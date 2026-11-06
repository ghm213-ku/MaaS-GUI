import pytest
import numpy as np
import json
from unittest import mock
import requests
import websocket
from hardware.worker import CountRateWorker
from hardware.coincidences_worker import CoincidencesWorker


@pytest.fixture(autouse=True)
def mock_channels_get(mocker):
    """Ensure Session.get('/channels') returns available channels by default across tests."""
    mock_get = mocker.patch("requests.Session.get")
    get_resp = mocker.Mock()
    get_resp.status_code = 200
    get_resp.json.return_value = {"channels": []}
    mock_get.return_value = get_resp
    return mock_get


@pytest.fixture(autouse=True)
def prevent_atexit_teardown(mocker):
    """Prevent registering atexit handlers in unit tests so test exit doesn't hang."""
    mocker.patch("atexit.register")


def test_worker_initialization_and_booking(mocker):
    # Mock requests.post for successful booking
    mock_post = mocker.patch("requests.Session.post")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp
    
    worker = CountRateWorker([1, 2], "testuser", int(1e9), 1000, 25)
    
    # Assert post was called correctly
    mock_post.assert_called_once_with(
        f"{worker.base_url}/channels/book",
        json={"user_name": "testuser", "channel_numbers": [1, 2]},
        timeout=2
    )
    assert worker.booking_error is None


def test_worker_booking_conflict(mocker):
    # Mock requests.post to raise 409
    mock_post = mocker.patch("requests.Session.post")
    error_resp = mocker.Mock()
    error_resp.status_code = 409
    
    def raise_409(*args, **kwargs):
        err = requests.exceptions.HTTPError()
        err.response = error_resp
        raise err
        
    mock_post.side_effect = raise_409
    
    # Mock requests.get to return conflicting channels
    mock_get = mocker.patch("requests.Session.get")
    get_resp = mocker.Mock()
    get_resp.json.return_value = {
        "channels": [
            {"channel_number": 1, "status": "booked", "user_name": "alice"}
        ]
    }
    mock_get.return_value = get_resp
    
    worker = CountRateWorker([1], "testuser", int(1e9), 1000, 25)
    
    assert worker.booking_error == "Channels are already booked by: alice"


def test_worker_run_measurement_start(mocker):
    mocker.patch("requests.Session.post") # Mock booking
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


def test_worker_teardown(mocker):
    mocker.patch("requests.Session.post")
    worker = CountRateWorker([1], "testuser", int(1e9), 1000, 25)
    worker.measurement_id = "test_id"
    worker.ws = mocker.Mock()
    
    mock_delete = mocker.patch("requests.Session.delete")
    mock_post = mocker.patch("requests.Session.post")
    
    worker._perform_teardown()
    
    worker.ws.close.assert_called_once()
    mock_delete.assert_called_once_with(f"{worker.base_url}/measurements/test_id", timeout=10)
    mock_post.assert_called_once_with(f"{worker.base_url}/channels/release/testuser", timeout=10)


# ================= CoincidencesWorker Tests =================

def test_coincidences_worker_initialization_with_list_of_lists(mocker):
    mock_post = mocker.patch("requests.Session.post")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    worker = CoincidencesWorker(
        coincidences=[[1, 2], [2, 3]],
        user_name="testuser",
        coincidence_window=1500,
    )

    assert worker.coincidences == [[1, 2], [2, 3]]
    assert worker.channels == [1, 2, 3]
    assert worker.coincidence_window == 1500
    mock_post.assert_called_once_with(
        f"{worker.base_url}/channels/book",
        json={"user_name": "testuser", "channel_numbers": [1, 2, 3]},
        timeout=2,
    )


def test_coincidences_worker_initialization_with_1d_channels(mocker):
    mock_post = mocker.patch("requests.Session.post")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    # Passing 1D channel list is automatically normalized to list of lists [[1, 2]]
    worker = CoincidencesWorker(
        channels=[1, 2],
        user_name="testuser",
        coincidence_window=2000,
    )

    assert worker.coincidences == [[1, 2]]
    assert worker.channels == [1, 2]
    assert worker.coincidence_window == 2000
    mock_post.assert_called_once_with(
        f"{worker.base_url}/channels/book",
        json={"user_name": "testuser", "channel_numbers": [1, 2]},
        timeout=2,
    )


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


def test_coincidences_worker_mock_mode(qtbot):
    worker = CoincidencesWorker(
        coincidences=[[1, 2]],
        is_mock=True,
        mode="Repeating",
    )
    data_received = []
    worker.newDataReady.connect(lambda d: data_received.append(d))

    worker.start()
    qtbot.waitUntil(lambda: len(data_received) >= 1, timeout=2000)
    worker.stop()
    worker.wait(1000)

    assert len(data_received) >= 1
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


def test_coincidences_worker_mock_mode_multiple_streams(qtbot):
    worker = CoincidencesWorker(
        coincidences=[[1, 2], [2, 3], [1, 3]],
        is_mock=True,
        mode="Free Running",
    )
    data_received = []
    stream_received = []
    worker.newDataReady.connect(lambda d: data_received.append(d))
    worker.streamDataReady.connect(lambda idx, arr: stream_received.append((idx, arr)))

    worker.start()
    qtbot.waitUntil(lambda: len(data_received) >= 1, timeout=2000)
    worker.stop()
    worker.wait(1000)

    assert len(data_received) >= 1
    assert data_received[0].shape == (3, 1)
    assert len(stream_received) >= 3


