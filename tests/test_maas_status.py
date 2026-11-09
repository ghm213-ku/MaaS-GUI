"""Tests for the MaaS connection/health panel on the home page."""
import base64
import json
from datetime import datetime

import pytest
import requests
from PyQt6.QtWidgets import QMessageBox

from hardware import health
from hardware.health import check_maas_health
from ui.main_window import MainWindow


def _resp(mocker, status_code=200, payload=None):
    resp = mocker.Mock()
    resp.status_code = status_code
    if payload is None:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = payload
    return resp


# ---- check_maas_health -------------------------------------------------------

def test_health_live(mocker):
    get = mocker.patch.object(health.requests, "get",
                              return_value=_resp(mocker, 200, {"status": "healthy", "version": "2.0", "nested": {"x": 1}}))
    r = check_maas_health("http://host:8000")
    get.assert_called_once_with("http://host:8000/health", timeout=2.0)
    assert r["state"] == "live" and r["live"]
    assert r["status"] == "healthy"
    assert r["details"] == {"version": "2.0"}  # nested values are dropped
    assert r["latency_ms"] is not None and r["error"] is None


def test_health_live_without_json(mocker):
    mocker.patch.object(health.requests, "get", return_value=_resp(mocker, 200, None))
    r = check_maas_health("http://host:8000")
    assert r["state"] == "live" and r["status"] is None


def test_health_degraded(mocker):
    mocker.patch.object(health.requests, "get", return_value=_resp(mocker, 200, {"status": "redis unavailable"}))
    r = check_maas_health("http://host:8000")
    assert r["state"] == "degraded"
    assert r["status"] == "redis unavailable"


def test_health_http_error(mocker):
    mocker.patch.object(health.requests, "get", return_value=_resp(mocker, 503, {"detail": "down"}))
    r = check_maas_health("http://host:8000")
    assert r["state"] == "error" and not r["live"]
    assert r["http_status"] == 503 and r["error"] == "HTTP 503"


def test_health_offline_uses_blocked_network():
    # The autouse conftest guard makes every real request raise ConnectionError.
    r = check_maas_health("http://host:8000")
    assert r["state"] == "offline" and not r["live"]
    assert r["error"] == "Connection refused or host unreachable"
    assert r["latency_ms"] is None


def test_health_timeout(mocker):
    mocker.patch.object(health.requests, "get", side_effect=requests.exceptions.ConnectTimeout())
    assert check_maas_health("http://h")["error"] == "Connection timed out"


# ---- MainWindow panel --------------------------------------------------------

def _result(window, **overrides):
    r = {"server_url": window.server_url, "state": "live", "live": True, "status": "healthy",
         "http_status": 200, "latency_ms": 12.3, "details": {"version": "2.0"}, "error": None,
         "checked_at": datetime(2026, 11, 9, 14, 5, 7)}
    r.update(overrides)
    return r


def _login(window, mocker, role="operator", exp=None):
    payload = {"sub": 1, "role": role}
    if exp is not None:
        payload["exp"] = exp
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    login_resp = mocker.Mock(status_code=200)
    login_resp.json.return_value = {"token": f"h.{b64}.s"}
    mocker.patch("requests.post", return_value=login_resp)
    window.login_username_input.setText("alice")
    window.login_password_input.setText("pw")
    window.authenticate()


def test_panel_is_on_home_page(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.tabs.widget(0) is window.setup_tab
    assert window.maas_status_panel.parent() is window.setup_tab
    assert window.maas_state_label.text() == "Checking…"
    assert window.server_url in window.maas_details_label.text()


def test_no_health_check_before_login(qtbot, fake_health_checks):
    window = MainWindow()
    qtbot.addWidget(window)
    fake_health_checks.assert_not_called()
    assert not window.health_timer.isActive()


def test_login_starts_health_check_and_timer(qtbot, mocker, mock_maas_channels, fake_health_checks):
    window = MainWindow()
    qtbot.addWidget(window)
    _login(window, mocker, exp=4102444800)  # 2100-01-01
    fake_health_checks.assert_called_once_with(window, window.server_url)
    assert window.health_timer.isActive()
    assert not window.btn_refresh_maas_status.isEnabled()

    window.on_maas_health_result(_result(window))
    assert window.maas_state_label.text() == "Live"
    assert window.btn_refresh_maas_status.isEnabled()
    details = window.maas_details_label.text()
    for expected in ("12 ms", "healthy", "Version", "2.0", "alice (operator)", "Session expires", "2100-01-01"):
        assert expected in details
    assert window.maas_last_checked_label.text() == "Checked 14:05:07"
    window.health_timer.stop()


@pytest.mark.parametrize("state,label", [("offline", "Offline"), ("error", "Error"), ("degraded", "Degraded")])
def test_unhealthy_states_are_shown(qtbot, state, label):
    window = MainWindow()
    qtbot.addWidget(window)
    window.refresh_maas_status()
    window.on_maas_health_result(_result(window, state=state, error="Connection timed out", latency_ms=None))
    assert window.maas_state_label.text() == label
    assert "Connection timed out" in window.maas_details_label.text()


def test_refresh_is_not_started_twice(qtbot, fake_health_checks):
    window = MainWindow()
    qtbot.addWidget(window)
    window.refresh_maas_status()
    window.refresh_maas_status()
    assert fake_health_checks.call_count == 1


def test_stale_result_for_old_server_triggers_recheck(qtbot, fake_health_checks):
    window = MainWindow()
    qtbot.addWidget(window)
    window.refresh_maas_status()
    stale = _result(window, server_url="http://old-server:8000")
    window.on_maas_health_result(stale)
    assert window.maas_health is None
    assert fake_health_checks.call_count == 2


def test_testing_mode_never_checks_network(qtbot, fake_health_checks):
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    window.login_username_input.setText("bob")
    window.login_password_input.setText("pw")
    window.authenticate()
    fake_health_checks.assert_not_called()
    assert not window.health_timer.isActive()
    assert window.maas_state_label.text() == "Testing mode"
    assert "test data" in window.maas_details_label.text()


def test_close_stops_health_timer(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.health_timer.start()
    window.close()
    assert not window.health_timer.isActive()


# ---- server address ----------------------------------------------------------

def test_entered_server_ip_is_used():
    from hardware.worker import normalize_server_url
    assert normalize_server_url("192.168.1.5") == ("http://192.168.1.5:8000", "ws://192.168.1.5:8000")
    assert normalize_server_url("myhost:9000") == ("http://myhost:9000", "ws://myhost:9000")


def test_blank_server_ip_falls_back_to_default():
    from hardware.worker import normalize_server_url, DEFAULT_SERVER_IP
    assert DEFAULT_SERVER_IP == "10.51.49.251"
    assert normalize_server_url("  ")[0] == "http://10.51.49.251:8000"
    assert normalize_server_url()[0] == "http://10.51.49.251:8000"


def test_window_defaults_and_ip_change(qtbot, monkeypatch):
    monkeypatch.delenv("MAAS_IP", raising=False)
    monkeypatch.delenv("MAAS_HOST", raising=False)
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.login_server_ip_input.text() == "10.51.49.251"
    assert window.server_url == "http://10.51.49.251:8000"
    window.set_server_ip("192.168.1.5")
    assert window.server_url == "http://192.168.1.5:8000"
    assert window.api_url == "http://192.168.1.5:8000/api/v1"
