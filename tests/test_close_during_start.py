"""Closing the GUI while a measurement is starting must still stop it on MaaS.

The measurement ID only arrives when the start request returns (~2 s of
hardware init). A teardown requested before then (window close, Stop) has
nothing to stop yet, so the worker must stop the measurement itself once the
ID arrives, and send the stop exactly once however many teardowns are asked.
"""
import pytest

from hardware.worker import CountRateWorker
from hardware.histogram_worker import HistogramWorker
from hardware.coincidences_worker import CoincidencesWorker
from ui.main_window import MainWindow

WORKERS = [
    lambda: CountRateWorker([1], "testuser", int(1e9), 1000, 25),
    lambda: HistogramWorker(1, 2, "testuser", 1000, 100, "Histogram"),
    lambda: CoincidencesWorker(coincidences=[[1, 2]], user_name="testuser", coincidence_window=1000),
]
IDS = ["count_rate", "histogram", "coincidences"]


@pytest.fixture(autouse=True)
def no_atexit(mocker):
    mocker.patch("atexit.register")


@pytest.fixture
def booked(mocker):
    resp = mocker.Mock(status_code=200)
    resp.json.return_value = {"channels": [
        {"channel_number": ch, "status": "booked", "user_name": "testuser"} for ch in range(1, 9)
    ]}
    mocker.patch("requests.Session.get", return_value=resp)


def start_response(mocker, measurement_id="m-123"):
    resp = mocker.Mock()
    resp.json.return_value = {"measurement_id": measurement_id}
    return resp


@pytest.mark.parametrize("make_worker", WORKERS, ids=IDS)
def test_close_while_starting_stops_measurement(mocker, booked, make_worker):
    worker = make_worker()
    delete = mocker.patch("requests.Session.delete")
    ws_class = mocker.patch("websocket.WebSocket")

    def post_while_closing(*args, **kwargs):
        # The window closes while MaaS is still initialising the hardware.
        worker.force_teardown()
        delete.assert_not_called()  # no ID yet, nothing to stop
        return start_response(mocker)

    mocker.patch("requests.Session.post", side_effect=post_while_closing)

    worker.run()

    delete.assert_called_once_with(f"{worker.base_url}/measurements/m-123", timeout=10)
    ws_class.return_value.connect.assert_not_called()


@pytest.mark.parametrize("make_worker", WORKERS, ids=IDS)
def test_measurement_is_stopped_only_once(mocker, booked, make_worker):
    worker = make_worker()
    worker.measurement_id = "m-123"
    delete = mocker.patch("requests.Session.delete")

    worker.force_teardown()
    worker._finish_run()
    worker.force_teardown()

    delete.assert_called_once()


def test_close_event_lets_workers_finish_stopping(qtbot, mocker):
    mocker.patch.object(MainWindow, "fetch_booked_channels")
    window = MainWindow()
    qtbot.addWidget(window)

    calls = []
    worker = mocker.MagicMock()
    worker.isRunning.return_value = True
    worker.stop.side_effect = lambda: calls.append("stop")
    worker.wait.side_effect = lambda ms: calls.append(("wait", ms)) or True
    worker.force_teardown.side_effect = lambda: calls.append("force_teardown")
    window.worker = worker

    window.close()

    assert calls[0] == "stop"
    assert calls[1][0] == "wait" and calls[1][1] > 15000  # room for start + stop
    assert calls[2] == "force_teardown"
