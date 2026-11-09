import pytest
import numpy as np
import json
from unittest import mock
import requests
import websocket
from hardware.worker import CountRateWorker
from hardware.coincidences_worker import CoincidencesWorker
from hardware.histogram_worker import HistogramWorker


def channels_response(mocker, channels):
    resp = mocker.Mock()
    resp.status_code = 200
    resp.json.return_value = {"channels": channels}
    return resp


@pytest.fixture(autouse=True)
def mock_channels_get(mocker):
    """By default Session.get('/channels') reports channels 1-8 booked by 'testuser'."""
    mock_get = mocker.patch("requests.Session.get")
    mock_get.return_value = channels_response(mocker, [
        {"channel_number": ch, "status": "booked", "user_name": "testuser"} for ch in range(1, 9)
    ])
    return mock_get


@pytest.fixture(autouse=True)
def prevent_atexit_teardown(mocker):
    """Prevent registering atexit handlers in unit tests so test exit doesn't hang."""
    mocker.patch("atexit.register")


def test_worker_with_booked_channels_does_not_book(mocker, mock_channels_get):
    mock_post = mocker.patch("requests.Session.post")

    worker = CountRateWorker([1, 2], "testuser", int(1e9), 1000, 25)

    assert worker.booking_error is None
    mock_channels_get.assert_called_once_with(f"{worker.base_url}/channels", timeout=2)
    mock_post.assert_not_called()  # booking only happens via the home page Book button


def test_worker_unbooked_channels_rejected(mocker, mock_channels_get):
    mock_post = mocker.patch("requests.Session.post")
    mock_channels_get.return_value = channels_response(mocker, [
        {"channel_number": 1, "status": "booked", "user_name": "testuser"},
        {"channel_number": 2, "status": "available", "user_name": None},
    ])

    worker = CountRateWorker([1, 2, 3], "testuser", int(1e9), 1000, 25)

    assert worker.booking_error is not None
    assert "[2, 3] are not booked" in worker.booking_error
    assert "home page" in worker.booking_error
    mock_post.assert_not_called()


def test_worker_channels_booked_by_other_user_rejected(mocker, mock_channels_get):
    mock_post = mocker.patch("requests.Session.post")
    mock_channels_get.return_value = channels_response(mocker, [
        {"channel_number": 1, "status": "booked", "user_name": "alice"},
    ])

    worker = CountRateWorker([1], "testuser", int(1e9), 1000, 25)

    assert "[1] are booked by alice" in worker.booking_error
    mock_post.assert_not_called()


def test_worker_backend_error_is_reported(mocker, mock_channels_get):
    mock_channels_get.side_effect = requests.exceptions.ConnectionError("unreachable")

    worker = CountRateWorker([1], "testuser", int(1e9), 1000, 25)

    assert worker.is_mock is False
    assert "MaaS backend request failed" in worker.booking_error


def test_worker_run_measurement_start(mocker):
    worker = CountRateWorker([1], "testuser", int(1e9), 1000, 25)
    
    # Mock post for measurement start
    mock_post = mocker.patch("requests.Session.post")
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {"measurement_id": "test_id"}
    mock_post.return_value = mock_resp
    
    # Mock websocket
    mock_ws_class = mocker.patch("websocket.WebSocket")
    mock_ws_instance = mocker.Mock()
    mock_ws_class.return_value = mock_ws_instance
    
    # Let the loop run once and exit
    def mock_recv():
        worker.running = False # break the loop
        return json.dumps({"data": [[1.0]*1000]})
    
    mock_ws_instance.recv.side_effect = mock_recv
    
    # Mock teardown to prevent actual HTTP calls during cleanup
    mocker.patch.object(worker, "_perform_teardown")
    
    worker.run()
    
    # Assert measurement was started with correct payload
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == f"{worker.base_url}/measurements/count-rate-live"
    payload = kwargs["json"]
    assert payload["metadata"]["refresh_rate"] == 25
    assert payload["metadata"]["user_name"] == "testuser"
    assert payload["metadata"]["channels"] == [1]


def test_worker_teardown_stops_measurement_but_keeps_channels(mocker):
    worker = CountRateWorker([1], "testuser", int(1e9), 1000, 25)
    worker.measurement_id = "test_id"
    worker.ws = mocker.Mock()
    
    mock_delete = mocker.patch("requests.Session.delete")
    mock_post = mocker.patch("requests.Session.post")
    
    worker._perform_teardown()
    
    worker.ws.close.assert_called_once()
    mock_delete.assert_called_once_with(f"{worker.base_url}/measurements/test_id", timeout=10)
    mock_post.assert_not_called()  # channels are only released via the home page Release button


@pytest.mark.parametrize("worker_factory", [
    lambda: CountRateWorker([1], "testuser", int(1e9), 1000, 25),
    lambda: HistogramWorker(1, 2, "testuser", 1000, 100, "Histogram"),
    lambda: CoincidencesWorker(coincidences=[[1, 2]], user_name="testuser", coincidence_window=1000),
], ids=["count_rate", "histogram", "coincidences"])
def test_no_worker_books_or_releases_channels(mocker, worker_factory):
    mock_post = mocker.patch("requests.Session.post")
    mocker.patch("requests.Session.delete")

    worker = worker_factory()
    assert worker.booking_error is None
    worker.measurement_id = "test_id"
    worker._perform_teardown()

    posted_urls = [c.args[0] for c in mock_post.call_args_list]
    assert not any("/channels/book" in u or "/channels/release" in u for u in posted_urls)


# ================= CoincidencesWorker Tests =================

def test_coincidences_worker_initialization_with_list_of_lists(mocker):
    mock_post = mocker.patch("requests.Session.post")

    worker = CoincidencesWorker(
        coincidences=[[1, 2], [2, 3]],
        user_name="testuser",
        coincidence_window=1500,
    )

    assert worker.coincidences == [[1, 2], [2, 3]]
    assert worker.channels == [1, 2, 3]
    assert worker.coincidence_window == 1500
    assert worker.booking_error is None
    mock_post.assert_not_called()


def test_coincidences_worker_initialization_with_1d_channels(mocker):
    mock_post = mocker.patch("requests.Session.post")

    # Passing 1D channel list is automatically normalized to list of lists [[1, 2]]
    worker = CoincidencesWorker(
        channels=[1, 2],
        user_name="testuser",
        coincidence_window=2000,
    )

    assert worker.coincidences == [[1, 2]]
    assert worker.channels == [1, 2]
    assert worker.coincidence_window == 2000
    assert worker.booking_error is None
    mock_post.assert_not_called()


@pytest.mark.parametrize("groups,expected_channels", [
    ([[1, 1]], [1]),                       # repeated channel within a group
    ([[1, 2, 1]], [1, 2]),
    ([[1, 2, 3], [2, 3, 4]], [1, 2, 3, 4]),  # channels shared across groups
    ([[101, 201]], [101, 201]),            # high Swabian channel IDs
])
def test_coincidences_worker_keeps_groups_and_derives_unique_channels(mocker, groups, expected_channels):
    """Groups are kept as given; the channels to check for booking are the unique, sorted set."""
    worker = CoincidencesWorker(coincidences=groups, user_name="testuser", coincidence_window=1000)

    assert worker.coincidences == groups
    assert worker.channels == expected_channels


def test_coincidences_worker_run_measurement_start(mocker):
    mocker.patch("requests.Session.post")
    worker = CoincidencesWorker(
        coincidences=[[1, 2]],
        user_name="testuser",
        coincidence_window=1200,
        refresh_rate=30,
    )

    mock_post = mocker.patch("requests.Session.post")
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {"measurement_id": "coinc_id_123"}
    mock_post.return_value = mock_resp

    mock_ws_class = mocker.patch("websocket.WebSocket")
    mock_ws_instance = mocker.Mock()
    mock_ws_class.return_value = mock_ws_instance

    received_arrays = []
    worker.newDataReady.connect(lambda arr: received_arrays.append(arr))

    def mock_recv():
        worker.running = False
        return json.dumps({"data": [123.0]})

    mock_ws_instance.recv.side_effect = mock_recv
    mocker.patch.object(worker, "_perform_teardown")

    worker.run()

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == f"{worker.base_url}/measurements/coincidences-live"
    payload = kwargs["json"]
    assert payload["measurement_type"] == "coincidences_live"
    assert payload["metadata"]["coincidences"] == [[1, 2]]
    assert payload["metadata"]["coincidence_window"] == 1200
    assert payload["metadata"]["refresh_rate"] == 30
    assert payload["metadata"]["user_name"] == "testuser"
    assert len(received_arrays) == 1
    assert received_arrays[0].shape == (1, 1)


def run_until_first_frame(worker, mocker):
    """Run the worker loop synchronously in this thread and stop after the first frame.

    No QThread is started: run() is called directly, signals are delivered
    immediately (same thread) and sleeping between frames is skipped.
    """
    mocker.patch("time.sleep")
    data_received = []
    stream_received = []

    def on_data(d):
        data_received.append(d)
        worker.running = False

    worker.newDataReady.connect(on_data)
    worker.streamDataReady.connect(lambda idx, arr: stream_received.append((idx, arr)))
    worker.run()
    return data_received, stream_received


def test_coincidences_worker_mock_mode(mocker):
    worker = CoincidencesWorker(
        coincidences=[[1, 2]],
        is_mock=True,
        mode="Repeating",
    )

    data_received, _ = run_until_first_frame(worker, mocker)

    assert len(data_received) == 1
    assert data_received[0].shape == (1, 1)


def test_coincidences_worker_multi_stream_websocket(mocker):
    mocker.patch("requests.Session.get")
    mocker.patch("requests.Session.post")
    worker = CoincidencesWorker(
        coincidences=[[1, 2], [2, 3]],
        user_name="testuser",
        coincidence_window=1000,
        refresh_rate=25,
    )

    mock_post = mocker.patch("requests.Session.post")
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {"measurement_id": "multi_coinc_id"}
    mock_post.return_value = mock_resp

    mock_ws_class = mocker.patch("websocket.WebSocket")
    mock_ws_instance = mocker.Mock()
    mock_ws_class.return_value = mock_ws_instance

    received_arrays = []
    received_streams = []
    worker.newDataReady.connect(lambda arr: received_arrays.append(arr))
    worker.streamDataReady.connect(lambda idx, arr: received_streams.append((idx, arr)))

    def mock_recv():
        worker.running = False
        return json.dumps({
            "type": "coincidences_live",
            "status_id": "multi_coinc_id",
            "coincidences": [[1, 2], [2, 3]],
            "virtual_channels": [20, 21],
            "streams": [
                {"stream_index": 0, "coincidence": [1, 2], "virtual_channel": 20, "rate": 1542.0, "data": 1542.0},
                {"stream_index": 1, "coincidence": [2, 3], "virtual_channel": 21, "rate": 28.5, "data": 28.5}
            ],
            "data": [1542.0, 28.5],
            "timestamp": "2026-10-29T12:00:00"
        })

    mock_ws_instance.recv.side_effect = mock_recv
    mocker.patch.object(worker, "_perform_teardown")

    worker.run()

    assert len(received_arrays) == 1
    assert received_arrays[0].shape == (2, 1)
    assert received_arrays[0][0, 0] == 1542.0
    assert received_arrays[0][1, 0] == 28.5

    assert len(received_streams) == 2
    assert received_streams[0][0] == 0
    assert received_streams[0][1][0] == 1542.0
    assert received_streams[1][0] == 1
    assert received_streams[1][1][0] == 28.5


def test_coincidences_worker_per_stream_websocket(mocker):
    mocker.patch("requests.Session.get")
    mocker.patch("requests.Session.post")
    worker = CoincidencesWorker(
        coincidences=[[1, 2], [2, 3]],
        user_name="testuser",
        stream_index=1,
    )

    mock_post = mocker.patch("requests.Session.post")
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {"measurement_id": "sub_coinc_id"}
    mock_post.return_value = mock_resp

    mock_ws_class = mocker.patch("websocket.WebSocket")
    mock_ws_instance = mocker.Mock()
    mock_ws_class.return_value = mock_ws_instance

    received_streams = []
    worker.streamDataReady.connect(lambda idx, arr: received_streams.append((idx, arr)))

    def mock_recv():
        worker.running = False
        return json.dumps({
            "type": "coincidences_live_stream",
            "status_id": "sub_coinc_id",
            "stream_index": 1,
            "coincidence": [2, 3],
            "virtual_channel": 21,
            "rate": 77.5,
            "data": 77.5,
            "timestamp": "2026-10-29T12:00:00"
        })

    mock_ws_instance.recv.side_effect = mock_recv
    mocker.patch.object(worker, "_perform_teardown")

    worker.run()

    mock_ws_instance.connect.assert_called_once()
    assert ":stream_1" in mock_ws_instance.connect.call_args[0][0]
    assert len(received_streams) == 1
    assert received_streams[0][0] == 1
    assert received_streams[0][1][0] == 77.5


def test_coincidences_worker_mock_mode_multiple_streams(mocker):
    worker = CoincidencesWorker(
        coincidences=[[1, 2], [2, 3], [1, 3]],
        is_mock=True,
        mode="Free Running",
    )

    data_received, stream_received = run_until_first_frame(worker, mocker)

    assert len(data_received) == 1
    assert data_received[0].shape == (3, 1)
    assert [idx for idx, _ in stream_received] == [0, 1, 2]


