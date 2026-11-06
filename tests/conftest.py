"""Shared pytest fixtures.

Unit tests must never talk to a live MaaS backend. The autouse fixture below
blocks every real HTTP request (via ``requests``) and websocket connection, so
any call a test has not explicitly mocked fails fast with a connection error
instead of reaching the network. Tests that need a backend response mock
``requests.Session.get``/``post``/... or ``websocket.WebSocket`` themselves;
those mocks replace the methods wholesale and therefore bypass this guard.
"""
import pytest
import requests
import websocket


class NetworkBlocked(requests.exceptions.ConnectionError):
    """Raised when a unit test tries to reach the real MaaS backend."""


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    attempts = []

    def blocked_request(self, method, url, *args, **kwargs):
        attempts.append((method, url))
        raise NetworkBlocked(f"Network access is blocked in unit tests: {method} {url}")

    def blocked_ws_connect(self, url, *args, **kwargs):
        attempts.append(("WS", url))
        raise NetworkBlocked(f"Network access is blocked in unit tests: websocket {url}")

    def blocked_create_connection(url, *args, **kwargs):
        attempts.append(("WS", url))
        raise NetworkBlocked(f"Network access is blocked in unit tests: websocket {url}")

    # requests.get/post/... and Session.get/post/... all funnel into Session.request.
    monkeypatch.setattr(requests.Session, "request", blocked_request)
    monkeypatch.setattr(websocket.WebSocket, "connect", blocked_ws_connect)
    monkeypatch.setattr(websocket, "create_connection", blocked_create_connection)

    return attempts


@pytest.fixture
def mock_maas_channels(mocker):
    """Mock the MaaS channel listing (GET /api/v1/channels) with no booked channels.

    MainWindow fetches the channel list when it is created outside testing mode,
    so tests that build a real (non force_mock) window use this fixture.
    """
    mock_get = mocker.patch("requests.Session.get")
    resp = mocker.Mock()
    resp.status_code = 200
    resp.json.return_value = {"channels": []}
    mock_get.return_value = resp
    return mock_get
