"""Stopped workers must stay referenced until their QThread has finished.

Dropping the last reference to a running QThread makes Qt abort the process
with "QThread: Destroyed while thread is still running" (seen after Stop then
Reset on the histogram tab).
"""
from unittest.mock import MagicMock

from ui.main_window import MainWindow


def make_running_worker():
    worker = MagicMock()
    worker.isRunning.return_value = True
    worker.wait.return_value = True
    return worker


def finish(worker):
    """Simulate the thread exiting: mark it stopped and fire finished slots."""
    worker.isRunning.return_value = False
    for call in worker.finished.connect.call_args_list:
        call.args[0]()


def test_stop_then_reset_histogram_keeps_worker_until_finished(qtbot, mocker):
    mocker.patch.object(MainWindow, "fetch_booked_channels")
    window = MainWindow()
    qtbot.addWidget(window)

    worker = make_running_worker()
    window.hist_worker = worker

    window.stop_histogram_measurement()
    assert window.hist_worker is None
    worker.stop.assert_called_once()
    assert worker in window.old_workers  # still referenced while tearing down

    window.reset_histogram_measurement()
    assert worker in window.old_workers

    finish(worker)
    assert worker not in window.old_workers


def test_stale_finished_signal_does_not_clear_new_worker(qtbot, mocker):
    mocker.patch.object(MainWindow, "fetch_booked_channels")
    window = MainWindow()
    qtbot.addWidget(window)

    old, new = make_running_worker(), make_running_worker()
    window.hist_worker = new
    mocker.patch.object(window, "sender", return_value=old)

    window.on_histogram_worker_finished()
    assert window.hist_worker is new


def test_all_tabs_retire_workers_instead_of_dropping_them(qtbot, mocker):
    mocker.patch.object(MainWindow, "fetch_booked_channels")
    window = MainWindow()
    qtbot.addWidget(window)

    for attr, stop in [
        ("worker", window.stop_measurement),
        ("coinc_worker", window.stop_coincidences_measurement),
    ]:
        worker = make_running_worker()
        setattr(window, attr, worker)
        stop()
        assert getattr(window, attr) is None
        assert worker in window.old_workers
