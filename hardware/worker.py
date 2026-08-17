import numpy as np
import json
import requests
import websocket
from PyQt6.QtCore import QThread, pyqtSignal

class CountRateWorker(QThread):
    """
    Background thread dedicated to interacting with the MaaS API via Redis Pub/Sub.
    """
    newDataReady = pyqtSignal(np.ndarray)

    def __init__(self, channels, user_name="maas-gui-client", binwidth=int(1e9), n_values=1000, duration_minutes=60, refresh_rate=25):
        super().__init__()
        self.channels = channels
        self.running = True
        self.user_name = user_name
        self.binwidth = binwidth
        self.n_values = n_values
        self.duration_minutes = duration_minutes
        self.refresh_rate = refresh_rate
        self.base_url = "http://localhost:8000/api/v1"
        self.ws_base_url = "ws://localhost:8000/api/v1"
        self.measurement_id = None
        self.ws = None
        self.is_paused = False
        self.booking_error = None

        # Book channels with a slight retry in case an old worker is still tearing down
        for attempt in range(5):
            try:
                resp = requests.post(f"{self.base_url}/channels/book", json={
                    "user_name": self.user_name,
                    "channel_numbers": self.channels
                })
                resp.raise_for_status()
                break
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 409:
                    # Check who booked the channels
                    try:
                        channels_info = requests.get(f"{self.base_url}/channels").json().get("channels", [])
                        conflict_users = set()
                        for ch_info in channels_info:
                            if ch_info["channel_number"] in self.channels and ch_info.get("status") == "booked":
                                # Only report conflict if it's a different user
                                if ch_info.get("user_name") != self.user_name:
                                    conflict_users.add(ch_info.get("user_name", "Unknown"))
                        
                        if conflict_users:
                            self.booking_error = f"Channels are already booked by: {', '.join(conflict_users)}"
                            break
                        else:
                            # They are booked by US! We can proceed.
                            break
                    except Exception as inner_e:
                        print(f"Failed to check channel status: {inner_e}")
                
                if attempt == 4:
                    print(f"Failed to book channels: {e}")
            except Exception as e:
                if attempt == 4:
                    print(f"Failed to book channels (they might already be booked or backend is down): {e}")
                else:
                    import time
                    time.sleep(0.2)

    def run(self):
        try:
            # 1. Start the measurement
            payload = {
                "measurement_type": "count_rate_live",
                "duration_seconds": self.duration_minutes * 60,
                "metadata": {
                    "channels": self.channels,
                    "user_name": self.user_name,
                    "binwidth": int(self.binwidth),
                    "n_values": int(self.n_values),
                    "refresh_rate": self.refresh_rate
                }
            }
            resp = requests.post(f"{self.base_url}/measurements/count-rate-live", json=payload)
            resp.raise_for_status()
            data = resp.json()
            self.measurement_id = data.get("measurement_id")

            if not self.measurement_id:
                print("No measurement_id returned by the API!")
                return

            # 2. Connect to WebSocket stream
            ws_url = f"{self.ws_base_url}/measurements/stream/{self.measurement_id}"
            self.ws = websocket.create_connection(ws_url)
            
            timeout_val = 1.0 / self.refresh_rate if self.refresh_rate > 0 else 0.04
            self.ws.settimeout(timeout_val)

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
                                
                            if rates_arr.shape[0] == len(self.channels):
                                # Emit the raw counts per bin directly (num_channels, n_values)
                                self.newDataReady.emit(rates_arr)
                        except Exception as e:
                            print(f"Error parsing websocket message: {e}")
                except websocket.WebSocketTimeoutException:
                    pass
                except websocket.WebSocketConnectionClosedException:
                    if self.running:
                        print("WebSocket closed by server.")
                    break
                
        except Exception as e:
            print(f"Hardware/Network Error: {e}")
        finally:
            self._perform_teardown()

    def _perform_teardown(self):
        if getattr(self, '_teardown_done', False):
            return
        self._teardown_done = True

        # Close WebSocket
        if self.ws:
            try:
                self.ws.close()
            except:
                pass

        # Stop measurement
        if self.measurement_id:
            try:
                # Use a timeout so it doesn't hang forever
                requests.delete(f"{self.base_url}/measurements/{self.measurement_id}", timeout=2)
            except Exception as e:
                print(f"Failed to stop measurement: {e}")

        # Release channels
        try:
            requests.post(f"{self.base_url}/channels/release/{self.user_name}", timeout=2)
        except Exception as e:
            print(f"Failed to release channels: {e}")
            
    def force_teardown(self):
        """Called by the GUI on exit to ensure teardown runs synchronously before process death."""
        self.running = False
        self._perform_teardown()
        
    def stop(self):
        self.running = False
        # Do not call self.wait() or HTTP requests here!
        # They will run in the finally block of the background thread to prevent blocking the GUI.
