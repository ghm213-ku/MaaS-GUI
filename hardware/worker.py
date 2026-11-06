import numpy as np
import json
import requests
import websocket
import logging
from PyQt6.QtCore import QThread, pyqtSignal
import atexit

logger = logging.getLogger(__name__)


def normalize_server_url(server_ip="127.0.0.1", default_port=8000):
    """
    Normalizes a server IP address, hostname, or URL string into HTTP and WebSocket base URLs.
    """
    # if not server_ip or not str(server_ip).strip():
    #     server_ip = "127.0.0.1"
    server_ip = "10.51.49.251"
    raw = str(server_ip).strip()

    if raw.startswith("http://") or raw.startswith("https://"):
        http_url = raw.rstrip("/")
        ws_url = "wss://" + http_url[8:] if http_url.startswith("https://") else "ws://" + http_url[7:]
    elif raw.startswith("ws://") or raw.startswith("wss://"):
        ws_url = raw.rstrip("/")
        http_url = "https://" + ws_url[6:] if ws_url.startswith("wss://") else "http://" + ws_url[5:]
    else:
        if ":" in raw:
            host_port = raw
        else:
            host_port = f"{raw}:{default_port}"
        http_url = f"http://{host_port}"
        ws_url = f"ws://{host_port}"

    return http_url, ws_url



def check_channels_booked(session, base_url, channels, user_name):
    """Verify that every channel in ``channels`` is already booked by ``user_name``.

    Workers never book (or release) channels themselves: booking and releasing
    only happen when the user clicks Book / Release on the home page. Returns
    an error message for the user, or None if all channels are booked by them.
    Raises requests.exceptions.RequestException if MaaS cannot be queried.
    """
    resp = session.get(f"{base_url}/channels", timeout=2)
    resp.raise_for_status()
    channels_info = {c.get("channel_number"): c for c in resp.json().get("channels", [])}

    not_booked = []
    booked_by_others = {}
    for ch in channels:
        info = channels_info.get(ch)
        if not info or info.get("status") != "booked":
            not_booked.append(ch)
        elif info.get("user_name") != user_name:
            booked_by_others.setdefault(info.get("user_name") or "Unknown", []).append(ch)

    problems = []
    if not_booked:
        problems.append(f"Channel(s) {not_booked} are not booked.")
    for other, chs in booked_by_others.items():
        problems.append(f"Channel(s) {chs} are booked by {other}.")
    if problems:
        return (" ".join(problems) +
                f" Book the channels as '{user_name}' on the home page before starting a measurement.")
    return None


class CountRateWorker(QThread):
    """
    Background thread dedicated to interacting with the MaaS API via Redis Pub/Sub.
    """
    newDataReady = pyqtSignal(np.ndarray)

    def __init__(self, channels, user_name="maas-gui-client", binwidth=int(1e9), n_values=1000, refresh_rate=25, mode="Free Running", auth_token="", is_mock=False, server_ip="127.0.0.1"):
        super().__init__()
        self.channels = channels
        self.running = True
        self.user_name = user_name
        self.binwidth = binwidth
        self.n_values = n_values
        self.refresh_rate = refresh_rate
        self.mode = mode
        self.server_ip = server_ip
        http_url, ws_url = normalize_server_url(server_ip)
        self.base_url = f"{http_url}/api/v1"
        self.ws_base_url = f"{ws_url}/api/v1"
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

        # Channels must already be booked by this user via the home page;
        # the worker never books channels itself.
        if self.is_mock:
            return

        try:
            self.booking_error = check_channels_booked(self.session, self.base_url, self.channels, self.user_name)
        except requests.exceptions.RequestException as e:
            logger.error(f"MaaS backend request failed ({e}). Cannot start CountRateWorker.")
            self.booking_error = f"MaaS backend request failed: {e}"
        if self.booking_error:
            logger.warning(f"CountRateWorker not started: {self.booking_error}")

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
                "measurement_type": "count_rate_live",
                "metadata": {
                    "channels": self.channels,
                    "user_name": self.user_name,
                    "binwidth": payload_binwidth,
                    "n_values": payload_n_values,
                    "refresh_rate": payload_refresh
                }
            }
            logger.info(f"Sending measurement request to backend API (this may take ~2 seconds for hardware init). Mode: {self.mode}")
            resp = self.session.post(f"{self.base_url}/measurements/count-rate-live", json=payload)
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

        # Channels stay booked: they are only released via the Release button on the home page.
            
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
