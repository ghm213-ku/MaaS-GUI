import numpy as np
import json
import requests
import websocket
import logging
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

class HistogramWorker(QThread):
    """
    Background thread dedicated to interacting with the MaaS API via Redis Pub/Sub.
    """
    newDataReady = pyqtSignal(np.ndarray, np.ndarray)
    
    def __init__(self, start_channel, click_channel, user_name, binwidth, n_values, duration_minutes, mode):
        super().__init__()
        self.running = True
        self.start_channel = start_channel
        self.click_channel = click_channel
        self.channels = list(set([start_channel, click_channel])) # Ensure unique channels
        self.user_name = user_name
        self.binwidth = binwidth
        self.n_values = n_values
        self.duration_minutes = duration_minutes
        self.mode = mode
        self.base_url = "http://127.0.0.1:8000/api/v1"
        self.ws_base_url = "ws://127.0.0.1:8000/api/v1"
        self.measurement_id = None
        self.ws = None
        self.is_paused = False
        self.booking_error = None
        self.is_mock = False
        
        # Book channels with a slight retry in case an old worker is still tearing down
        for attempt in range(5):
            try:
                resp = requests.get(f"{self.base_url}/channels", timeout=2)
                resp.raise_for_status()
                channels_info = resp.json().get("channels", [])
                
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
                    resp = requests.post(f"{self.base_url}/channels/book", json={
                        "user_name": self.user_name,
                        "channel_numbers": channels_to_book
                    }, timeout=2)
                    resp.raise_for_status()
                    
                # If we got here, all requested channels are booked by us
                break
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Backend unavailable ({e}). Enabling mock mode for HistogramWorker.")
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
            # mode string mapping (e.g. "Start-Stop" -> "start-stop-live")
            endpoint_map = {
                "Start-Stop": "startstop-live",
                "Histogram": "histogram-live",
                "Correlation": "correlation-live"
            }
            meas_type = endpoint_map.get(self.mode, "histogram-live")
            payload_duration = self.duration_minutes * 60

            if self.mode == "Correlation":
                metadata = {
                    "channel1": self.start_channel,
                    "channel2": self.click_channel,
                    "user_name": self.user_name,
                    "binwidth": int(self.binwidth),
                    "n_bins": int(self.n_values),
                    "refresh_rate": 25
                }
            else:
                metadata = {
                    "start_channel": self.start_channel,
                    "click_channel": self.click_channel,
                    "user_name": self.user_name,
                    "binwidth": int(self.binwidth),
                    "n_bins": int(self.n_values),
                    "refresh_rate": 25
                }

            payload = {
                "measurement_type": meas_type.replace("-", "_"),
                "duration_seconds": payload_duration,
                "metadata": metadata
            }
            logger.info(f"Sending histogram measurement request to backend API. Mode: {self.mode}")
            resp = requests.post(f"{self.base_url}/measurements/{meas_type}", json=payload)
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
            self.ws.connect(ws_url, timeout=10.0)
            self.ws.settimeout(2.0)
            logger.info("WebSocket connected successfully!")
            
            import time
            start_time = None
            
            while self.running:
                try:
                    msg = self.ws.recv()
                    if msg and not self.is_paused:
                        try:
                            msg_data = json.loads(msg)
                            if isinstance(msg_data, dict) and "data" in msg_data:
                                rates_raw = msg_data.get("data", [])
                                index_raw = msg_data.get("index", [])
                            else:
                                rates_raw = msg_data
                                index_raw = []

                            rates_arr = np.array(rates_raw)
                            index_arr = np.array(index_raw)
                            
                            if start_time is None:
                                start_time = time.time()
                                logger.info(f"First data frame received from Redis stream via WebSocket (shape: {rates_arr.shape})")
                                
                            # Emit the raw 1D histogram arrays
                            self.newDataReady.emit(index_arr, rates_arr)
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
        logger.info(f"Running mock HistogramWorker in mode: {self.mode}")
        refresh_interval = 1.0 / 25.0
        
        while self.running:
            if not self.is_paused:
                index_arr = np.arange(self.n_values) * self.binwidth
                
                center = self.n_values // 2
                x = np.arange(self.n_values)
                
                if self.mode == "Correlation":
                    sigma = max(1, self.n_values / 10)
                    rates_arr = 1000 * np.exp(-0.5 * ((x - center) / sigma) ** 2) + np.random.poisson(lam=10, size=self.n_values)
                else:
                    sigma = max(1, self.n_values / 20)
                    rates_arr = 500 * np.exp(-0.5 * ((x - center/2) / sigma) ** 2) + np.random.poisson(lam=5, size=self.n_values)
                
                self.newDataReady.emit(index_arr, rates_arr)
                
            time.sleep(refresh_interval)

    def _perform_teardown(self):
        if getattr(self, '_teardown_done', False):
            return
        self._teardown_done = True
        
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
                    requests.delete(f"{self.base_url}/measurements/{self.measurement_id}", timeout=10)
                    logger.info(f"Successfully stopped measurement {self.measurement_id}")
                    break
                except Exception as e:
                    logger.error(f"Failed to stop measurement (attempt {attempt+1}): {e}")

        # Release channels
        for attempt in range(2):
            try:
                requests.post(f"{self.base_url}/channels/release/{self.user_name}", timeout=10)
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
        # Do not call self.wait() or HTTP requests here!
        # They will run in the finally block of the background thread to prevent blocking the GUI.
