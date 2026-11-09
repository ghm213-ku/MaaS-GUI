"""The GUI's side of the MaaS contract.

- Correlation sends the click channel as channel1 and the start channel as channel2.
- Single mode sends duration_seconds (MaaS uses Time Tagger startFor) and stops on
  the frame MaaS flags "final", not on its own wall clock.
- WebSocket streams send the login token.
- set-parameters waits for the queued job and reports failures.
- Trigger/delay labels are read back from MaaS (GET /channels/parameters).
- Creating a user tells the admin the initial password.
"""
import json
from unittest.mock import Mock

import pytest

from hardware.coincidences_worker import CoincidencesWorker
from hardware.histogram_worker import HistogramWorker
from hardware.worker import CountRateWorker
from ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def booked_channels(mocker):
    """Session.get('/channels/') reports channels 1-8 booked by 'testuser'."""
    resp = Mock(status_code=200)
    resp.json.return_value = {"channels": [
        {"channel_number": ch, "status": "booked", "user_name": "testuser"} for ch in range(1, 9)
    ]}
    return mocker.patch("requests.Session.get", return_value=resp)


@pytest.fixture(autouse=True)
def no_atexit(mocker):
    mocker.patch("atexit.register")


def run_worker(mocker, worker, frames):
    """Run ``worker`` against a fake MaaS that streams ``frames`` (dicts) over the WebSocket.

    Returns (posted_payload, ws_mock). The loop is also ended once frames run out.
    """
    post = mocker.patch("requests.Session.post")
    post.return_value.json.return_value = {"measurement_id": "mid"}
    ws = Mock()
    mocker.patch("websocket.WebSocket", return_value=ws)
    remaining = list(frames)

    def recv():
        if not remaining:
            worker.running = False
            return ""
        return json.dumps(remaining.pop(0))

    ws.recv.side_effect = recv
    mocker.patch.object(worker, "_perform_teardown")
    worker.run()
    return post.call_args.kwargs["json"], ws


# ---------- correlation channel order ----------

def test_correlation_sends_click_as_channel1_and_start_as_channel2(mocker):
    worker = HistogramWorker(start_channel=1, click_channel=2, user_name="testuser",
                             binwidth=100, n_values=10, mode="Correlation", auth_token="tok")

    payload, _ = run_worker(mocker, worker, [])

    assert payload["metadata"]["channel1"] == 2  # click (stop)
    assert payload["metadata"]["channel2"] == 1  # start


# ---------- Single mode ----------

def test_count_rate_single_sends_duration_and_stops_on_final_frame(mocker):
    worker = CountRateWorker([1], "testuser", binwidth=int(1e12), n_values=3, mode="Single")
    frames_seen = []
    worker.newDataReady.connect(lambda arr: frames_seen.append(arr.copy()))

    payload, _ = run_worker(mocker, worker, [
        {"data": [[1, 0, 0]], "final": False},
        {"data": [[1, 2, 3]], "final": True},
        {"data": [[9, 9, 9]], "final": False},  # must not be read
    ])

    assert payload["duration_seconds"] == pytest.approx(3.0)  # 3 bins of 1 s
    assert len(frames_seen) == 2
    assert frames_seen[-1].tolist() == [[1, 2, 3]]


def test_count_rate_free_running_sends_no_duration(mocker):
    worker = CountRateWorker([1], "testuser", binwidth=int(1e9), n_values=3, mode="Free Running")
    payload, _ = run_worker(mocker, worker, [])
    assert "duration_seconds" not in payload


def test_single_mode_does_not_stop_on_wall_clock_before_final(mocker):
    """A Single run with a tiny duration must keep reading until MaaS sends the final frame."""
    worker = CountRateWorker([1], "testuser", binwidth=1, n_values=1, mode="Single")
    frames_seen = []
    worker.newDataReady.connect(lambda arr: frames_seen.append(arr))

    run_worker(mocker, worker, [{"data": [[0]], "final": False}] * 3 + [{"data": [[5]], "final": True}])

    assert len(frames_seen) == 4


def test_coincidences_single_sends_duration_and_stops_on_final_frame(mocker):
    worker = CoincidencesWorker(coincidences=[[1, 2]], user_name="testuser",
                                binwidth=int(1e12), n_values=2, mode="Single")
    frames_seen = []
    worker.newDataReady.connect(lambda arr: frames_seen.append(arr.copy()))

    def frame(data, final):
        return {"type": "coincidences_live", "streams": [{"stream_index": 0, "data": data}],
                "data": [data], "final": final}

    payload, _ = run_worker(mocker, worker, [frame([0, 1], False), frame([4, 5], True), frame([7, 7], False)])

    assert payload["duration_seconds"] == pytest.approx(2.0)
    assert len(frames_seen) == 2
    assert frames_seen[-1].tolist() == [[4, 5]]


# ---------- WebSocket authentication ----------

@pytest.mark.parametrize("factory", [
    lambda: CountRateWorker([1], "testuser", auth_token="tok"),
    lambda: HistogramWorker(1, 2, "testuser", 100, 10, "Histogram", auth_token="tok"),
    lambda: CoincidencesWorker(coincidences=[[1, 2]], user_name="testuser", auth_token="tok"),
], ids=["count_rate", "histogram", "coincidences"])
def test_websocket_sends_login_token(mocker, factory):
    worker = factory()
    _, ws = run_worker(mocker, worker, [])
    assert ws.connect.call_args.kwargs["header"] == ["Authorization: Bearer tok"]


# ---------- home page: parameters ----------

def response(status_code=200, body=None):
    resp = Mock(status_code=status_code, text=json.dumps(body))
    resp.json.return_value = body
    return resp


@pytest.fixture
def window(qtbot, mocker):
    window = MainWindow()
    qtbot.addWidget(window)
    window.login_username = "testuser"
    mocker.patch("ui.main_window.time.sleep")
    return window


def route_get(mocker, window, routes):
    """Mock window.session.get, answering by URL suffix. Values may be lists (served in order)."""
    def get(url, **kwargs):
        for suffix, value in routes.items():
            if url.endswith(suffix):
                if isinstance(value, list):
                    return value.pop(0) if len(value) > 1 else value[0]
                return value
        raise AssertionError(f"unexpected GET {url}")
    return mocker.patch.object(window.session, "get", side_effect=get)


def test_labels_show_parameters_read_from_maas(window, mocker):
    route_get(mocker, window, {
        "/channels/": response(body={"channels": []}),
        "/channels/parameters": response(body={"channels": [
            {"channel_number": 12, "trigger_voltage": 0.0, "input_delay": 0},
            {"channel_number": 3, "trigger_voltage": 0.25, "input_delay": 400},
        ]}),
    })

    window.fetch_booked_channels()

    assert window.channel_nodes[12].node.lbl_trig.text() == "0.0V"
    assert (window.channel_nodes[3].node.trigger_val, window.channel_nodes[3].node.delay_val) == (0.25, 400)
    assert window.channel_nodes[1].node.lbl_trig.text() == "0.5V"  # not reported: unchanged


def test_missing_parameters_endpoint_keeps_labels(window, mocker):
    route_get(mocker, window, {
        "/channels/": response(body={"channels": []}),
        "/channels/parameters": response(404, {"detail": "Not Found"}),
    })
    window.fetch_booked_channels()
    assert window.channel_nodes[3].node.lbl_trig.text() == "0.5V"


def book(window, channel):
    window.channel_nodes[channel].set_booked_by("testuser", True)


def mock_set_parameters_post(mocker, window):
    return mocker.patch.object(window.session, "post",
                               return_value=response(201, {"measurement_id": "job1", "status": "queued"}))


def test_set_parameters_waits_for_job_to_complete(window, mocker):
    book(window, 3)
    mock_set_parameters_post(mocker, window)
    get = route_get(mocker, window, {
        "/measurements/job1/status": [response(body={"status": "queued"}), response(body={"status": "completed"})],
        "/channels/parameters": response(body={"channels": []}),
    })

    assert window.channel_nodes[3].node.set_parameters(1.25, 400) is True

    status_calls = [c for c in get.call_args_list if c.args[0].endswith("/measurements/job1/status")]
    assert len(status_calls) == 2
    assert window.channel_nodes[3].node.lbl_trig.text() == "1.25V"


def test_set_parameters_job_failure_is_reported(window, mocker):
    book(window, 3)
    mock_set_parameters_post(mocker, window)
    route_get(mocker, window, {
        "/measurements/job1/status": response(body={"status": "failed", "message": "Job failed: bad level"}),
        "/channels/parameters": response(body={"channels": []}),
    })
    warn = mocker.patch("ui.main_window.QMessageBox.warning")

    assert window.channel_nodes[3].node.set_parameters(9.9, 400) is False

    assert "Job failed: bad level" in warn.call_args[0][2]
    assert window.channel_nodes[3].node.lbl_trig.text() == "0.5V"


def test_set_parameters_not_confirmed_in_time(window, mocker):
    book(window, 3)
    window.PARAMETER_JOB_TIMEOUT_S = 0
    mock_set_parameters_post(mocker, window)
    route_get(mocker, window, {
        "/measurements/job1/status": response(body={"status": "queued"}),
        "/channels/parameters": response(body={"channels": []}),
    })
    warn = mocker.patch("ui.main_window.QMessageBox.warning")

    assert window.channel_nodes[3].node.set_parameters(1.0, 0) is False
    assert "not applied it yet" in warn.call_args[0][2]


def test_release_waits_for_reset_then_shows_maas_values(window, mocker):
    book(window, 3)
    window.channel_nodes[3].node.show_parameters(1.25, 400)
    window.channel_nodes[3].node.is_active = True
    mocker.patch.object(window.session, "post", return_value=response(200, {
        "user_name": "testuser", "released_channels": [3], "total_released": 1,
        "parameter_reset_id": "reset1",
    }))
    get = route_get(mocker, window, {
        "/measurements/reset1/status": response(body={"status": "completed"}),
        "/channels/": response(body={"channels": []}),
        "/channels/parameters": response(body={"channels": [
            {"channel_number": 3, "trigger_voltage": 0.5, "input_delay": 0},
        ]}),
    })

    window.release_channels()

    urls = [c.args[0] for c in get.call_args_list]
    assert urls.index(f"{window.api_url}/measurements/reset1/status") < urls.index(f"{window.api_url}/channels/parameters")
    assert (window.channel_nodes[3].node.trigger_val, window.channel_nodes[3].node.delay_val) == (0.5, 0)


# ---------- new users ----------

def test_new_user_message_states_initial_password(qtbot, mocker):
    window = MainWindow()
    qtbot.addWidget(window)
    window.build_add_user_tab()
    mocker.patch.object(window.session, "post", return_value=response(201, {
        "message": "User created successfully", "user_id": 5,
        "initial_password": "username",
        "initial_password_note": "The initial password is the username ('bob').",
    }))
    info = mocker.patch("PyQt6.QtWidgets.QMessageBox.information")

    window.new_user_username_input.setText("bob")
    window.submit_add_user()

    assert "initial password is the username ('bob')" in info.call_args[0][2]
    assert "Initial password" in window.add_user_status_label.text()
