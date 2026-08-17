import pytest
import numpy as np
import json
from unittest import mock
import requests
import websocket
from hardware.worker import CountRateWorker

def test_worker_initialization_and_booking(mocker):
    # Mock requests.post for successful booking
    mock_post = mocker.patch("requests.post")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp
    
    worker = CountRateWorker([1, 2], "testuser", int(1e9), 1000, 60, 25)
    
    # Assert post was called correctly
    mock_post.assert_called_once_with(
        "http://localhost:8000/api/v1/channels/book",
        json={"user_name": "testuser", "channel_numbers": [1, 2]}
    )
    assert worker.booking_error is None

def test_worker_booking_conflict(mocker):
    # Mock requests.post to raise 409
    mock_post = mocker.patch("requests.post")
    error_resp = mocker.Mock()
    error_resp.status_code = 409
    
    def raise_409(*args, **kwargs):
        err = requests.exceptions.HTTPError()
        err.response = error_resp
        raise err
        
    mock_post.side_effect = raise_409
    
    # Mock requests.get to return conflicting channels
    mock_get = mocker.patch("requests.get")
    get_resp = mocker.Mock()
    get_resp.json.return_value = {
        "channels": [
            {"channel_number": 1, "status": "booked", "user_name": "alice"}
        ]
    }
    mock_get.return_value = get_resp
    
    worker = CountRateWorker([1], "testuser", int(1e9), 1000, 60, 25)
    
    assert worker.booking_error == "Channels are already booked by: alice"

def test_worker_run_measurement_start(mocker):
    mocker.patch("requests.post") # Mock booking
    worker = CountRateWorker([1], "testuser", int(1e9), 1000, 60, 25)
    
    # Mock post for measurement start
    mock_post = mocker.patch("requests.post")
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {"measurement_id": "test_id"}
    mock_post.return_value = mock_resp
    
    # Mock websocket
    mock_ws = mocker.patch("websocket.create_connection")
    mock_ws_instance = mocker.Mock()
    mock_ws.return_value = mock_ws_instance
    
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
    assert args[0] == "http://localhost:8000/api/v1/measurements/count-rate-live"
    payload = kwargs["json"]
    assert payload["duration_seconds"] == 3600
    assert payload["metadata"]["refresh_rate"] == 25
    assert payload["metadata"]["user_name"] == "testuser"
    assert payload["metadata"]["channels"] == [1]

def test_worker_teardown(mocker):
    mocker.patch("requests.post")
    worker = CountRateWorker([1], "testuser", int(1e9), 1000, 60, 25)
    worker.measurement_id = "test_id"
    worker.ws = mocker.Mock()
    
    mock_delete = mocker.patch("requests.delete")
    mock_post = mocker.patch("requests.post")
    
    worker._perform_teardown()
    
    worker.ws.close.assert_called_once()
    mock_delete.assert_called_once_with("http://localhost:8000/api/v1/measurements/test_id", timeout=2)
    mock_post.assert_called_once_with("http://localhost:8000/api/v1/channels/release/testuser", timeout=2)
