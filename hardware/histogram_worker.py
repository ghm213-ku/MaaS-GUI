import numpy as np
import json
import requests
import websocket
import logging
from PyQt6.QtCore import QThread, pyqtSignal
import atexit
from hardware.worker import normalize_server_url, check_channels_booked, ws_auth_header, DEFAULT_SERVER_IP

logger = logging.getLogger(__name__)

# MaaS publishes the whole histogram (data + index, as JSON) every 1/refresh_rate s
# and relays it through Redis Pub/Sub to the WebSocket. If that outgrows what the
# relay can carry, Redis drops the subscriber after its output buffer fills (a few
# seconds) and the stream ends. Keep frames * size under a fixed budget.
MAX_REFRESH_RATE_HZ = 25
MIN_REFRESH_RATE_HZ = 1  # MaaS takes an integer refresh_rate
STREAM_BUDGET_BYTES_PER_S = 2_000_000
BYTES_PER_BIN_ESTIMATE = 20  # data + index values as JSON text

# Warn when no frame has arrived for this long (and at least a few frame periods).
STALL_WARNING_S = 5.0


def histogram_refresh_rate(n_bins):
    """Frames per second to request from MaaS for a histogram of ``n_bins`` bins."""
    frame_bytes = max(1, int(n_bins)) * BYTES_PER_BIN_ESTIMATE
    rate = STREAM_BUDGET_BYTES_PER_S // frame_bytes
    return int(min(MAX_REFRESH_RATE_HZ, max(MIN_REFRESH_RATE_HZ, rate)))


class HistogramWorker(QThread):
    """
    Background thread dedicated to interacting with the MaaS API via Redis Pub/Sub.
    """
    newDataReady = pyqtSignal(np.ndarray, np.ndarray)
    # Human-readable message when the stream stalls or the server closes it.
    streamProblem = pyqtSignal(str)

    def __init__(self, start_channel, click_channel, user_name, binwidth, n_values, mode, auth_token="", is_mock=False, server_ip=DEFAULT_SERVER_IP):
        super().__init__()
        self.running = True
        self.start_channel = start_channel
        self.click_channel = click_channel
        self.channels = list(set([start_channel, click_channel])) # Ensure unique channels
        self.user_name = user_name
        self.binwidth = binwidth
        self.n_values = n_values
        self.refresh_rate = histogram_refresh_rate(n_values)
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
            logger.error(f"MaaS backend request failed ({e}). Cannot start HistogramWorker.")
            self.booking_error = f"MaaS backend request failed: {e}"
        if self.booking_error:
            logger.warning(f"HistogramWorker not started: {self.booking_error}")

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

            if self.mode == "Correlation":
                # Time Tagger Correlation: channel_1 is the click (stop) channel and
                # channel_2 the start channel, so the delay axis is t(click) - t(start).
                metadata = {
                    "channel1": self.click_channel,
                    "channel2": self.start_channel,
                    "user_name": self.user_name,
                    "binwidth": int(self.binwidth),
                    "n_bins": int(self.n_values),
                    "refresh_rate": self.refresh_rate
                }
            else:
                metadata = {
                    "start_channel": self.start_channel,
                    "click_channel": self.click_channel,
                    "user_name": self.user_name,
                    "binwidth": int(self.binwidth),
                    "n_bins": int(self.n_values),
                    "refresh_rate": self.refresh_rate
                }

            if self.refresh_rate < MAX_REFRESH_RATE_HZ:
                logger.info(f"n_bins={self.n_values}: requesting {self.refresh_rate} Hz updates to keep the stream within budget")

            payload = {
                "measurement_type": meas_type.replace("-", "_"),
                "metadata": metadata
            }
            logger.info(f"Sending histogram measurement request to backend API. Mode: {self.mode}")
            resp = self.session.post(f"{self.base_url}/measurements/{meas_type}", json=payload)
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
            self.ws.connect(ws_url, timeout=10.0, header=ws_auth_header(self.auth_token))
            self.ws.settimeout(2.0)
            logger.info("WebSocket connected successfully!")
            
            import time
            start_time = None
            last_frame_time = time.monotonic()
            stall_after_s = max(STALL_WARNING_S, 3.0 / self.refresh_rate)
            stall_reported = False

            while self.running:
                try:
                    msg = self.ws.recv()
                    if msg:
                        last_frame_time = time.monotonic()
                        if stall_reported:
                            logger.info("Histogram stream resumed.")
                            stall_reported = False
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
                            logger.exception(f"Error parsing websocket message: {e}")
                except websocket.WebSocketTimeoutException:
                    silent_s = time.monotonic() - last_frame_time
                    if self.running and not stall_reported and silent_s >= stall_after_s:
                        stall_reported = True
                        message = (f"No histogram data from MaaS for {silent_s:.0f} s. "
                                   f"Try fewer bins (n_values={self.n_values}).")
                        logger.warning(message)
                        self.streamProblem.emit(message)
                except websocket.WebSocketConnectionClosedException:
                    if self.running:
                        message = "MaaS closed the histogram data stream."
                        logger.warning(message)
                        self.streamProblem.emit(message)
                    break
                
        except Exception as e:
            logger.exception(f"Hardware/Network Error: {e}")
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
