"""Saving a channel's trigger/delay on the home page sends POST /api/v1/set-parameters/ to MaaS."""
import pytest
import requests
from ui.main_window import ChannelConfigPopup, MainWindow

pytestmark = pytest.mark.usefixtures("mock_maas_channels")


@pytest.fixture
def window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.login_username = "testuser"
    return window


def book(window, channel, user="testuser"):
    window.channel_nodes[channel].set_booked_by(user, user == "testuser")


def mock_post(mocker, window, status_code=201, text=""):
    post = mocker.patch.object(window.session, "post")
    resp = mocker.Mock()
    resp.status_code = status_code
    resp.text = text
    post.return_value = resp
    return post


def test_saving_parameters_sends_set_parameters_request(window, mocker):
    book(window, 3)
    post = mock_post(mocker, window)
    node = window.channel_nodes[3].node

    assert node.set_parameters(1.25, 400) is True

    post.assert_called_once()
    args, kwargs = post.call_args
    assert args[0] == f"{window.api_url}/set-parameters/"
    assert kwargs["json"] == {
        "measurement_type": "set_parameters",
        "duration_seconds": 0,
        "metadata": {
            "channels": [3],
            "user_name": "testuser",
            "trigger_voltage": 1.25,
            "input_delay": 400,
        },
    }
    assert (node.trigger_val, node.delay_val) == (1.25, 400)
    assert node.lbl_trig.text() == "1.25V"
    assert node.lbl_dly.text() == "400ps"


@pytest.mark.parametrize("booked_by", [None, "alice"])
def test_parameters_not_sent_for_channel_not_booked_by_user(window, mocker, booked_by):
    if booked_by:
        book(window, 3, booked_by)
    post = mock_post(mocker, window)
    warn = mocker.patch("ui.main_window.QMessageBox.warning")
    node = window.channel_nodes[3].node

    assert node.set_parameters(1.25, 400) is False

    post.assert_not_called()
    assert warn.called and "not booked by you" in warn.call_args[0][2]
    assert (node.trigger_val, node.delay_val) == (0.5, 0)


def test_rejected_parameters_are_not_kept(window, mocker):
    book(window, 3)
    mock_post(mocker, window, status_code=422, text="invalid trigger")
    warn = mocker.patch("ui.main_window.QMessageBox.warning")
    node = window.channel_nodes[3].node

    assert node.set_parameters(9.9, 400) is False

    assert warn.called and "invalid trigger" in warn.call_args[0][2]
    assert (node.trigger_val, node.delay_val) == (0.5, 0)
    assert node.lbl_trig.text() == "0.5V"


def test_backend_unreachable_parameters_are_not_kept(window, mocker):
    book(window, 3)
    post = mocker.patch.object(window.session, "post", side_effect=requests.exceptions.ConnectionError("down"))
    crit = mocker.patch("ui.main_window.QMessageBox.critical")
    node = window.channel_nodes[3].node

    assert node.set_parameters(1.0, 100) is False

    post.assert_called_once()
    assert crit.called
    assert (node.trigger_val, node.delay_val) == (0.5, 0)


def test_testing_mode_does_not_contact_maas(qtbot, mocker):
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    post = mocker.patch.object(window.session, "post")
    node = window.channel_nodes[3].node

    assert node.set_parameters(1.0, 100) is True

    post.assert_not_called()
    assert (node.trigger_val, node.delay_val) == (1.0, 100)


@pytest.mark.parametrize("trigger,delay,expected", [
    ("1,5", "200", (1.5, 200)),
    ("abc", "200", None),
    ("1.5", "2.5", None),
    ("", "", None),
])
def test_popup_parse_values(qtbot, trigger, delay, expected):
    popup = ChannelConfigPopup(0.5, 0)
    qtbot.addWidget(popup)
    popup.trigger_input.setText(trigger)
    popup.delay_input.setText(delay)
    assert popup.parse_values() == expected
