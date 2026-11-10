import numpy as np
import json
import requests
import websocket
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from hardware.worker import (
    BackendTeardownMixin,
    normalize_server_url, check_channels_booked, ws_auth_header, single_duration_seconds,
    SINGLE_FINAL_FRAME_GRACE_S, DEFAULT_SERVER_IP,
)

logger = logging.getLogger(__name__)

class CoincidencesWorker(BackendTeardownMixin, QThread):
    """
    Background thread dedicated to interacting with the MaaS API via Redis Pub/Sub.
    """
    newDataReady = pyqtSignal(np.ndarray)
    streamDataReady = pyqtSignal(int, np.ndarray)

    def __init__(
        self,
        channels=None,
        user_name="maas-gui-client",
        binwidth=int(1e9),
        n_values=1000,
        refresh_rate=25,
        mode="Free Running",
        auth_token="",
        is_mock=False,
        coincidences=None,
        coincidence_window=1000,
        timestamp="Last",
        stream_index=None,
        server_ip=DEFAULT_SERVER_IP,
    ):
        super().__init__()
        # Normalize coincidences input into list of lists: [[ch1, ch2, ...], ...]
        raw_groups = None
        if coincidences is not None:
            raw_groups = coincidences
        elif channels is not None:
            if isinstance(channels, (list, tuple)) and len(channels) > 0 and isinstance(channels[0], (list, tuple)):
                raw_groups = channels
            elif isinstance(channels, (list, tuple)):
                raw_groups = [channels]
            else:
                raw_groups = []
        else:
            raw_groups = []

        self.coincidences = [[int(ch) for ch in group] for group in raw_groups]
        # Collect unique channel numbers across all coincidence groups for channel booking
        self.channels = sorted(list({int(ch) for group in self.coincidences for ch in group}))

        self.running = True
        self.user_name = user_name
        self.coincidence_window = int(coincidence_window)
        self.timestamp = timestamp
        self.binwidth = binwidth
        self.n_values = n_values
        self.refresh_rate = refresh_rate
        self.mode = mode
        self.stream_index = stream_index
        self.latest_streams = []
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
        
        self._init_teardown()

        # Channels must already be booked by this user via the home page;
        # the worker never books channels itself.
        if self.is_mock:
            return

        try:
            self.booking_error = check_channels_booked(self.session, self.base_url, self.channels, self.user_name)
        except requests.exceptions.RequestException as e:
            logger.error(f"MaaS backend request failed ({e}). Cannot start CoincidencesWorker.")
            self.booking_error = f"MaaS backend request failed: {e}"
        if self.booking_error:
            logger.warning(f"CoincidencesWorker not started: {self.booking_error}")

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
                self.exact_duration_sec = single_duration_seconds(self.binwidth, self.n_values)
                payload_binwidth = int(self.binwidth)
                payload_n_values = int(self.n_values)
                payload_refresh = self.refresh_rate # Use standard refresh rate
            else: # Free Running
                payload_binwidth = int(self.binwidth)
                payload_n_values = int(self.n_values)
                payload_refresh = self.refresh_rate

            payload = {
                "measurement_type": "coincidences_live",
                **({"duration_seconds": self.exact_duration_sec} if self.mode == "Single" else {}),
                "metadata": {
                    "coincidences": self.coincidences,
                    "coincidence_window": self.coincidence_window,
                    "timestamp": self.timestamp,
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
            if self._stopped_while_starting():
                return

            # 2. Connect to WebSocket stream
            if self.stream_index is not None:
                ws_url = f"{self.ws_base_url}/measurements/stream/{self.measurement_id}:stream_{self.stream_index}"
            else:
                ws_url = f"{self.ws_base_url}/measurements/stream/{self.measurement_id}"
            logger.info(f"Connecting to WebSocket: {ws_url}")
            self.ws = websocket.WebSocket()
            # Give the backend up to 10 seconds to accept the connection (hardware init can be slow)
            self.ws.connect(ws_url, timeout=10.0, header=ws_auth_header(self.auth_token))
            # Reduce timeout for the recv loop so it checks self.running frequently
            self.ws.settimeout(2.0)
            logger.info("WebSocket connected successfully!")
            
            import time
            start_time = None
            
            while self.running:
                if (self.mode == "Single" and start_time is not None
                        and time.time() - start_time > self.exact_duration_sec + SINGLE_FINAL_FRAME_GRACE_S):
                    logger.warning("Single acquisition: no final frame from MaaS. Stopping worker.")
                    self.running = False
                    break
                try:
                    msg = self.ws.recv()
                    if msg and not self.is_paused:
                        try:
                            msg_data = json.loads(msg)
                            # Last frame of a timed (Single) acquisition: the counter has finished
                            is_final = isinstance(msg_data, dict) and bool(msg_data.get("final"))
                            num_coinc = len(self.coincidences) if self.coincidences else (len(self.channels) if self.channels else 1)

                            # Handle dedicated per-stream message: {"type": "coincidences_live_stream", "stream_index": i, "rate": ..., "data": ...}
                            if isinstance(msg_data, dict) and msg_data.get("type") == "coincidences_live_stream":
                                s_idx = int(msg_data.get("stream_index", 0))
                                # "data" is the stream's full Counter buffer (n_values bins);
                                # "rate" (counts/s of the latest bin) is only a fallback.
                                s_val = msg_data.get("data", msg_data.get("rate", 0.0))
                                s_arr = np.array([s_val], dtype=float).flatten()
                                self.streamDataReady.emit(s_idx, s_arr)
                                
                                full_arr = np.zeros((num_coinc, len(s_arr)))
                                if s_idx < num_coinc:
                                    full_arr[s_idx] = s_arr
                                self.newDataReady.emit(full_arr)
                                if start_time is None:
                                    start_time = time.time()
                                if self.mode == "Single" and is_final:
                                    logger.info(f"Single acquisition ({self.exact_duration_sec}s) complete. Stopping worker.")
                                    self.running = False
                                    break
                                continue

                            # Multiplexed payload: {"type": "coincidences_live", "streams": [...], "data": [...]}
                            if isinstance(msg_data, dict):
                                if "streams" in msg_data and isinstance(msg_data["streams"], list) and len(msg_data["streams"]) > 0:
                                    self.latest_streams = msg_data["streams"]
                                    # Each stream's "data" is its Counter buffer: counts per bin, oldest first.
                                    rates_raw = [s.get("data", s.get("rate", 0.0)) for s in self.latest_streams]
                                elif "data" in msg_data:
                                    rates_raw = msg_data.get("data", [])
                                else:
                                    rates_raw = msg_data
                            else:
                                rates_raw = msg_data

                            rates_arr = np.array(rates_raw, dtype=float)
                            if rates_arr.ndim == 0:
                                rates_arr = rates_arr.reshape(1, 1)
                            elif rates_arr.ndim == 1:
                                if rates_arr.shape[0] == num_coinc:
                                    rates_arr = rates_arr.reshape(num_coinc, 1)
                                elif num_coinc == 1:
                                    rates_arr = rates_arr.reshape(1, -1)
                                else:
                                    rates_arr = rates_arr.reshape(min(num_coinc, rates_arr.shape[0]), -1)
                            elif rates_arr.ndim > 2:
                                rates_arr = rates_arr.reshape(num_coinc, -1)

                            if start_time is None:
                                start_time = time.time()
                                logger.info(f"First data frame received from Redis stream via WebSocket (shape: {rates_arr.shape})")

                            num_coinc = len(self.coincidences) if self.coincidences else len(self.channels)
                            if rates_arr.shape[0] == num_coinc or rates_arr.shape[0] == len(self.channels) or rates_arr.size > 0:
                                if self.mode == "Single":
                                    logger.info(f"Received Single frame, shape: {rates_arr.shape}, sum: {rates_arr.sum()}")
                                    
                                # Emit 2D array and per-stream data
                                self.newDataReady.emit(rates_arr)
                                for i in range(rates_arr.shape[0]):
                                    self.streamDataReady.emit(i, rates_arr[i])
                                
                                # Single mode: MaaS runs the counter for exactly n_values bins and
                                # flags the complete buffer as the final frame.
                                if self.mode == "Single" and is_final:
                                    logger.info(f"Single acquisition ({self.exact_duration_sec}s) complete. Stopping worker.")
                                    self.running = False
                                    break
                        except Exception as e:
                            logger.exception(f"Error parsing websocket message: {e}")
                except websocket.WebSocketTimeoutException:
                    pass
                except websocket.WebSocketConnectionClosedException:
                    if self.running:
                        logger.warning("WebSocket closed by server.")
                    break
                
        except Exception as e:
            logger.exception(f"Hardware/Network Error: {e}")
        finally:
            self._finish_run()

    def _run_mock(self):
        import time
        logger.info(f"Running mock CoincidencesWorker in mode: {self.mode}")
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
            
        num_items = len(self.coincidences) if getattr(self, 'coincidences', None) else (len(self.channels) if getattr(self, 'channels', None) else 1)
        if num_items == 0:
            num_items = 1

        if self.mode not in ("Repeating", "Single"):
            self._run_mock_rolling(num_items, refresh_interval)
            return

        while self.running:
            if not self.is_paused:
                if self.mode == "Repeating":
                    shape = (num_items, 1)
                elif self.mode == "Single":
                    shape = (num_items, self.n_values)
                else:
                    shape = (num_items, 1)
                    
                # Generate mock data with distinct rates per coincidence stream
                mock_data = np.zeros(shape)
                for i in range(num_items):
                    base_rate = 500.0 + (i * 350.0)
                    mock_data[i] = np.random.normal(loc=base_rate, scale=max(5.0, base_rate * 0.08), size=shape[1:])
                mock_data = np.clip(mock_data, 0, None)
                
                self.newDataReady.emit(mock_data)
                for i in range(num_items):
                    self.streamDataReady.emit(i, mock_data[i])
                
                if exact_duration_sec and (time.time() - start_time) >= exact_duration_sec:
                    logger.info("Single measurement duration complete. Stopping mock worker.")
                    self.running = False
                    break
                    
            time.sleep(refresh_interval)

    def _run_mock_rolling(self, num_items, refresh_interval):
        """Mimic the backend's live Counter: a rolling buffer of n_values bins
        of binwidth ps (oldest first) that gains one bin per elapsed binwidth."""
        import time
        n_values = max(1, int(self.n_values))
        binwidth_s = max(self.binwidth, 1) * 1e-12
        rates = [500.0 + i * 350.0 for i in range(num_items)]  # coincidences / s
        buffer = np.zeros((num_items, n_values))
        start_time = time.time()
        bins_done = 0
        while self.running:
            bins_now = int((time.time() - start_time) / binwidth_s)
            new_bins = min(bins_now - bins_done, n_values)
            bins_done = bins_now
            if new_bins > 0:
                buffer = np.roll(buffer, -new_bins, axis=1)
                for i in range(num_items):
                    buffer[i, -new_bins:] = np.random.poisson(rates[i] * binwidth_s, size=new_bins)
            if not self.is_paused:
                self.newDataReady.emit(buffer.copy())
                for i in range(num_items):
                    self.streamDataReady.emit(i, buffer[i].copy())
            time.sleep(refresh_interval)

        
    def stop(self):
        self.running = False
        if getattr(self, 'ws', None):
            try:
                self.ws.close()
            except Exception:
                pass

        # Do not call self.wait() or HTTP requests here!
        # They will run in the finally block of the background thread to prevent blocking the GUI.
