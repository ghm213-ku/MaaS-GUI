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

from hardware.worker import CountRateWorker
from hardware.histogram_worker import HistogramWorker
from hardware.coincidences_worker import CoincidencesWorker


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


class FakeWorkers:
    """Replaces the measurement workers used by MainWindow with mocks.

    The real workers are QThreads that talk to MaaS (or generate test data in
    testing mode). UI tests only need to know what the window asked for, so the
    worker classes in ``ui.main_window`` are swapped for MagicMocks: no thread is
    ever started and no data arrives unless a test pushes it explicitly.

    Attributes:
        count_rate / histogram / coincidences: the patched classes; inspect
            ``.call_args.kwargs`` to see how the window constructed the worker.
        created: every fake worker instance, in creation order.
        booking_error: value given to ``booking_error`` of workers created from
            now on (None means the channels are booked and the worker may start).
    """

    def __init__(self, mocker):
        self._mocker = mocker
        self.created = []
        self.booking_error = None
        self.count_rate = self._patch("CountRateWorker", CountRateWorker)
        self.histogram = self._patch("HistogramWorker", HistogramWorker)
        self.coincidences = self._patch("CoincidencesWorker", CoincidencesWorker)

    def _patch(self, name, real_cls):
        def create(*args, **kwargs):
            worker = self._mocker.MagicMock(spec=real_cls, name=f"Fake{name}")
            worker.booking_error = self.booking_error
            worker.is_paused = False
            worker.running = True
            self.created.append(worker)
            return worker

        return self._mocker.patch(f"ui.main_window.{name}", side_effect=create)


@pytest.fixture(autouse=True)
def fake_workers(mocker):
    """No test starts a real measurement worker through the GUI (see FakeWorkers).

    Worker behaviour itself is tested in test_worker.py, which uses the real
    classes from the ``hardware`` package directly.
    """
    return FakeWorkers(mocker)


@pytest.fixture(autouse=True)
def fake_health_checks(mocker):
    """The home page MaaS health check normally runs on a QThreadPool thread.

    Tests never start that thread: ``MainWindow._start_health_check`` is replaced
    by a mock recording the server URLs it was asked to check. Tests deliver a
    result themselves by calling ``window.on_maas_health_result(...)``.
    """
    from ui.main_window import MainWindow
    return mocker.patch.object(MainWindow, "_start_health_check", autospec=True)
