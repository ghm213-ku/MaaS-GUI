"""MaaS connection / health checking used by the home page status panel."""
import logging
import time
from datetime import datetime

import requests
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

logger = logging.getLogger(__name__)

# /health "status" values that mean the service is fully up.
HEALTHY_STATUSES = {"healthy", "ok", "up", "pass", "passing", "alive", "live", "running"}

STATE_LIVE = "live"
STATE_DEGRADED = "degraded"
STATE_ERROR = "error"
STATE_OFFLINE = "offline"


def check_maas_health(server_url, timeout=2.0):
    """Query ``GET {server_url}/health`` and summarise the result.

    Never raises. Returns a dict with:
        server_url, state (live/degraded/error/offline), live (bool),
        status (str from the payload, if any), http_status, latency_ms,
        details (other top-level scalar fields from the payload),
        error (str or None), checked_at (datetime).
    """
    result = {
        "server_url": server_url,
        "state": STATE_OFFLINE,
        "live": False,
        "status": None,
        "http_status": None,
        "latency_ms": None,
        "details": {},
        "error": None,
        "checked_at": datetime.now(),
    }
    start = time.perf_counter()
    try:
        # A plain request (not the window's shared Session) so this can run off the GUI thread.
        resp = requests.get(f"{server_url}/health", timeout=timeout)
    except requests.exceptions.RequestException as e:
        result["error"] = _short_error(e)
        return result

    result["latency_ms"] = (time.perf_counter() - start) * 1000.0
    result["http_status"] = resp.status_code

    payload = None
    try:
        payload = resp.json()
    except ValueError:
        pass

    if isinstance(payload, dict):
        status = payload.get("status")
        if status is not None:
            result["status"] = str(status)
        result["details"] = {
            k: v for k, v in payload.items()
            if k != "status" and isinstance(v, (str, int, float, bool))
        }
    elif isinstance(payload, str):
        result["status"] = payload

    if resp.status_code != 200:
        result["state"] = STATE_ERROR
        result["error"] = f"HTTP {resp.status_code}"
    elif result["status"] is None or result["status"].strip().lower() in HEALTHY_STATUSES:
        result["state"] = STATE_LIVE
        result["live"] = True
    else:
        result["state"] = STATE_DEGRADED
        result["live"] = True
    return result


def _short_error(exc):
    if isinstance(exc, requests.exceptions.ConnectTimeout) or isinstance(exc, requests.exceptions.ReadTimeout):
        return "Connection timed out"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "Connection refused or host unreachable"
    return str(exc) or exc.__class__.__name__


class HealthCheckSignals(QObject):
    finished = pyqtSignal(dict)


class HealthCheckTask(QRunnable):
    """Runs check_maas_health on a QThreadPool thread and emits the result."""

    def __init__(self, server_url, timeout=2.0):
        super().__init__()
        self.server_url = server_url
        self.timeout = timeout
        self.signals = HealthCheckSignals()

    def run(self):
        try:
            result = check_maas_health(self.server_url, self.timeout)
        except Exception as e:  # defensive: never let a pool thread die silently
            logger.exception("Health check failed unexpectedly")
            result = {"server_url": self.server_url, "state": STATE_OFFLINE, "live": False,
                      "status": None, "http_status": None, "latency_ms": None, "details": {},
                      "error": str(e), "checked_at": datetime.now()}
        self.signals.finished.emit(result)
