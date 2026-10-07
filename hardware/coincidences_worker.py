import numpy as np
import json
import requests
import websocket
import logging
from PyQt6.QtCore import QThread, pyqtSignal
import atexit

logger = logging.getLogger(__name__)

class CoincidencesWorker(QThread):
    """
    Background thread dedicated to interacting with the MaaS API via Redis Pub/Sub.
    """
    newDataReady = pyqtSignal(np.ndarray)

    def __init__(self, channels, user_name="maas-gui-client", binwidth=int(1e9), n_values=1000, refresh_rate=25, mode="Free Running", auth_token="", is_mock=False):
        super().__init__()
        self.channels = channels
        self.running = True
        self.user_name = user_name
        self.binwidth = binwidth
        self.n_values = n_values
        self.refresh_rate = refresh_rate
        self.mode = mode
        self.base_url = "http://127.0.0.1:8000/api/v1"
        self.ws_base_url = "ws://127.0.0.1:8000/api/v1"
        self.auth_token = auth_token
        self.session = requests.Session()
        if self.auth_token:
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        self.measurement_id = None
        self.ws = None
        self.is_paused = False
        self.booking_error = None
        self.is_mock = is_mock
        
        atexit.register(self.force_teardown)

        # Book channels with a slight retry
        if self.is_mock:
            return

        for attempt in range(5):
            try:
                # 1. Check current status of all requested channels
                channels_info = self.session.get(f"{self.base_url}/channels", timeout=2).json().get("channels", [])
                
                conflict_users = set()
                channels_to_book = []
                
                for ch in self.channels:
                    ch_status = next((c for c in channels_info if c["channel_number"] == ch), None)
                    if ch_status and ch_status.get("status") == "booked":
                        if ch_status.get("user_name") != self.user_name:
                            conflict_users.add(ch_status.get("user_name", "Unknown"))
                    else:
                        channels_to_book.append(ch)
                        
                if conflict_users:
                    logger.warning(f"MaaS API channel booking conflict: channels already used by {conflict_users}")
                    self.booking_error = f"Channels are already booked by: {', '.join(conflict_users)}"
                    break
                    
                # 2. Book ONLY the channels that are currently available
                if channels_to_book:
                    logger.info(f"Attempting to book {len(channels_to_book)} channels via MaaS API: {channels_to_book}")
                    resp = self.session.post(f"{self.base_url}/channels/book", json={
                        "user_name": self.user_name,
                        "channel_numbers": channels_to_book
                    }, timeout=2)
                    resp.raise_for_status()
                    
                # If we got here, all requested channels are booked by us
                break
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Backend unavailable ({e}). Enabling mock mode for CountRateWorker.")
                self.is_mock = True
                break
            except Exception as e:
                if attempt == 4:
                    logger.error(f"Failed to book channels: {e}")
                    self.booking_error = f"Failed to book channels: {e}"
                else:
                    import time
                    time.sleep(0.2)

    def run(self):
        if getattr(self, 'is_mock', False):
            self._run_mock()
            return
            
        try:
            # 1. Start the measurement
            # Configure payload based on mode
            if self.mode == "Repeating":
                payload_binwidth = int(self.binwidth)
                payload_n_values = 1 # Force exactly 1 bin
                payload_refresh = int(max(1, min(100, 1e12 / self.binwidth))) # Derive Hz from binwidth, bound between 1-100Hz
            elif self.mode == "Single":
                self.exact_duration_sec = (self.n_values * self.binwidth) / 1e12
                payload_binwidth = int(self.binwidth)
                payload_n_values = int(self.n_values)
                payload_refresh = self.refresh_rate # Use standard refresh rate
            else: # Free Running
                payload_binwidth = int(self.binwidth)
                payload_n_values = int(self.n_values)
                payload_refresh = self.refresh_rate

            payload = {
                "measurement_type": "coincidences_live",
                "metadata": {
                    "channels": self.channels,
                    "user_name": self.user_name,
                    "binwidth": payload_binwidth,
                    "n_values": payload_n_values,
                    "refresh_rate": payload_refresh
                }
            }
            logger.info(f"Sending measurement request to backend API (this may take ~2 seconds for hardware init). Mode: {self.mode}")
            resp = self.session.post(f"{self.base_url}/measurements/coincidences-live", json=payload)
            resp.raise_for_status()
            data = resp.json()
            self.measurement_id = data.get("status_id", data.get("measurement_id"))

            if not self.measurement_id:
                logger.error("No measurement_id returned by the API!")
                return

            # 2. Connect to WebSocket stream
            ws_url = f"{self.ws_base_url}/measurements/stream/{self.measurement_id}"
            logger.info(f"Connecting to WebSocket: {ws_url}")
            self.ws = websocket.WebSocket()
            # Give the backend up to 10 seconds to accept the connection (hardware init can be slow)
            self.ws.connect(ws_url, timeout=10.0)
            # Reduce timeout for the recv loop so it checks self.running frequently
            self.ws.settimeout(2.0)
            logger.info("WebSocket connected successfully!")
            
            import time
            start_time = None
            
            while self.running:
                try:
                    msg = self.ws.recv()
                    if msg and not self.is_paused:
                        try:
                            # Depending on if backend forwards raw redis string or re-serializes
                            msg_data = json.loads(msg)
                            # Handle both raw list and {"data": list} dictionary payload
                            if isinstance(msg_data, dict) and "data" in msg_data:
                                rates_raw = msg_data.get("data", [])
                            else:
                                rates_raw = msg_data

                            rates_arr = np.array(rates_raw)
                            
                            if rates_arr.ndim == 1:
                                # Reshape to 2D for consistency
                                rates_arr = rates_arr.reshape(-1, 1)
                                
                            if start_time is None:
                                start_time = time.time()
                                logger.info(f"First data frame received from Redis stream via WebSocket (shape: {rates_arr.shape})")
                                
                            if rates_arr.shape[0] == len(self.channels):
                                if self.mode == "Single":
                                    logger.info(f"Received Single frame, shape: {rates_arr.shape}, sum: {rates_arr.sum()}")
                                    
                                # Emit the raw counts per bin directly (num_channels, n_values)
                                self.newDataReady.emit(rates_arr)
                                
                                # If Single mode, stop after exact duration has elapsed
                                if self.mode == "Single" and (time.time() - start_time) >= self.exact_duration_sec:
                                    logger.info(f"Single measurement duration ({self.exact_duration_sec}s) complete. Stopping worker.")
                                    self.running = False
                                    break
                        except Exception as e:
                            logger.error(f"Error parsing websocket message: {e}")
                except websocket.WebSocketTimeoutException:
                    pass
                except websocket.WebSocketConnectionClosedException:
                    if self.running:
                        logger.warning("WebSocket closed by server.")
                    break
                
        except Exception as e:
            logger.error(f"Hardware/Network Error: {e}")
        finally:
            self._perform_teardown()

    def _run_mock(self):
        import time
        logger.info(f"Running mock CountRateWorker in mode: {self.mode}")
        start_time = time.time()
        
        if self.mode == "Repeating":
            refresh_interval = 1.0 / max(1, min(100, 1e12 / self.binwidth))
            exact_duration_sec = None
        elif self.mode == "Single":
            refresh_interval = 1.0 / self.refresh_rate
            exact_duration_sec = (self.n_values * self.binwidth) / 1e12
        else:
            refresh_interval = 1.0 / self.refresh_rate
            exact_duration_sec = None
            
        while self.running:
            if not self.is_paused:
                if self.mode == "Repeating":
                    shape = (len(self.channels), 1)
                else:
                    shape = (len(self.channels), self.n_values)
                    
                # Generate mock data
                mock_data = np.random.normal(loc=800, scale=100, size=shape)
                mock_data = np.clip(mock_data, 0, None)
                
                self.newDataReady.emit(mock_data)
                
                if exact_duration_sec and (time.time() - start_time) >= exact_duration_sec:
                    logger.info("Single measurement duration complete. Stopping mock worker.")
                    self.running = False
                    break
                    
            time.sleep(refresh_interval)

    def _perform_teardown(self):
        if getattr(self, '_teardown_done', False):
            return
        self._teardown_done = True
        
        try:
            atexit.unregister(self.force_teardown)
        except Exception:
            pass
        
        if getattr(self, 'is_mock', False):
            return

        # Close WebSocket
        if self.ws:
            try:
                self.ws.close()
            except:
                pass

        # Stop measurement
        if self.measurement_id:
            for attempt in range(2):
                try:
                    # Swabian hardware takes ~5.5s to teardown on the backend!
                    self.session.delete(f"{self.base_url}/measurements/{self.measurement_id}", timeout=10)
                    logger.info(f"Successfully stopped measurement {self.measurement_id}")
                    break
                except Exception as e:
                    logger.error(f"Failed to stop measurement (attempt {attempt+1}): {e}")

        # Release channels
        for attempt in range(2):
            try:
                self.session.post(f"{self.base_url}/channels/release/{self.user_name}", timeout=10)
                logger.info(f"Successfully released channels for {self.user_name}")
                break
            except Exception as e:
                logger.error(f"Failed to release channels (attempt {attempt+1}): {e}")
            
    def force_teardown(self):
        """Called by the GUI on exit to ensure teardown runs synchronously before process death."""
        self.running = False
        self._perform_teardown()
        
    def stop(self):
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        # Do not call self.wait() or HTTP requests here!
        # They will run in the finally block of the background thread to prevent blocking the GUI.
