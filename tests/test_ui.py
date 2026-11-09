import pytest
from PyQt6.QtCore import Qt
from ui.main_window import ChannelConfigPopup, ChannelNodeWidget, MainWindow

def test_channel_config_popup_get_values(qtbot):
    popup = ChannelConfigPopup(0.5, 100)
    qtbot.addWidget(popup)
    
    popup.trigger_input.setText("1.5")
    popup.delay_input.setText("200")
    
    t, d = popup.get_values()
    assert t == 1.5
    assert d == 200

def test_channel_config_popup_get_values_invalid(qtbot):
    popup = ChannelConfigPopup(0.5, 100)
    qtbot.addWidget(popup)
    
    popup.trigger_input.setText("invalid")
    popup.delay_input.setText("invalid")
    
    t, d = popup.get_values()
    assert t == 0.5
    assert d == 0

def test_channel_node_widget_toggle(qtbot):
    node = ChannelNodeWidget(1)
    qtbot.addWidget(node)
    
    assert not node.is_active
    qtbot.mouseClick(node, Qt.MouseButton.LeftButton)
    assert node.is_active
    qtbot.mouseClick(node, Qt.MouseButton.LeftButton)
    assert not node.is_active

def test_channel_node_widget_set_booked_by(qtbot):
    node = ChannelNodeWidget(1)
    qtbot.addWidget(node)
    
    node.set_booked_by("alice", False)
    assert node.booked_by == "alice"
    assert not node.is_active
    assert node.lbl_trig.isHidden()
    assert node.lbl_dly.isHidden()

def test_channel_node_widget_click_when_booked(qtbot):
    node = ChannelNodeWidget(1)
    qtbot.addWidget(node)
    
    node.set_booked_by("alice", False)
    qtbot.mouseClick(node, Qt.MouseButton.LeftButton)
    # Should not toggle
    assert not node.is_active

def test_main_window_initialization(qtbot, mocker):
    mock_get = mocker.patch("requests.Session.get")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"channels": []}
    mock_get.return_value = mock_resp
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    assert window.windowTitle() == "Swabian Count Rate Monitor"
    assert window.tabs.count() == 5
    assert len(window.channel_nodes) == 18

def test_main_window_start_measurement_no_channels(qtbot, mocker):
    mock_get = mocker.patch("requests.Session.get")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "healthy"}
    mock_get.return_value = mock_resp
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Mock QMessageBox to prevent blocking
    mocker.patch("ui.main_window.QMessageBox.warning")
    mocker.patch("ui.main_window.QMessageBox.critical")
    
    # Ensure no channels are active
    for node in window.channel_nodes.values():
        node.is_active = False
        
    window.btn_play_pause.click()
    
    import ui.main_window
    ui.main_window.QMessageBox.warning.assert_called_with(
        window, "No Channels", "Please select at least one channel from the Channels Setup tab."
    )

def test_main_window_fetch_booked_channels(qtbot, mocker):
    mock_get = mocker.patch("requests.Session.get")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "channels": [
            {"channel_number": 1, "status": "booked", "user_name": "bob"}
        ]
    }
    mock_get.return_value = mock_resp
    
    window = MainWindow()
    qtbot.addWidget(window)
    window.fetch_booked_channels()
    
    assert window.channel_nodes[1].full_user_name == "bob"


def _mock_login(mocker, token="login-token"):
    login = mocker.patch("requests.post")
    resp = mocker.Mock()
    resp.status_code = 200
    resp.json.return_value = {"token": token}
    login.return_value = resp
    return login


def test_channels_not_fetched_before_login(qtbot, mocker):
    """Before login there is no auth token, so the GUI must not query MaaS for channels."""
    mock_get = mocker.patch("requests.Session.get")

    window = MainWindow()
    qtbot.addWidget(window)

    channel_calls = [c for c in mock_get.call_args_list if "/channels" in str(c.args[0])]
    assert channel_calls == []


def test_login_fetches_channel_bookings(qtbot, mocker):
    """Logging in loads the current bookings from MaaS, using the new auth token."""
    window = MainWindow()
    qtbot.addWidget(window)
    _mock_login(mocker, token="login-token")

    seen_auth = []
    resp = mocker.Mock()
    resp.status_code = 200
    resp.json.return_value = {"channels": [
        {"channel_number": 2, "status": "booked", "user_name": "alice"},
        {"channel_number": 5, "status": "booked", "user_name": "bob"},
        {"channel_number": 7, "status": "available", "user_name": None},
    ]}

    def fake_get(url, **kwargs):
        seen_auth.append(window.session.headers.get("Authorization"))
        return resp

    mock_get = mocker.patch.object(window.session, "get", side_effect=fake_get)

    window.login_username_input.setText("alice")
    window.login_password_input.setText("secret")
    window.authenticate()

    mock_get.assert_called_once_with(f"{window.api_url}/channels", timeout=2)
    assert seen_auth == ["Bearer login-token"]
    assert window.channel_nodes[2].node.booked_by == "alice"
    assert window.channel_nodes[2].node.is_current_user
    assert window.channel_nodes[5].node.booked_by == "bob"
    assert not window.channel_nodes[5].node.is_current_user
    assert window.channel_nodes[7].node.booked_by is None


def test_failed_channel_fetch_after_login_is_handled(qtbot, mocker):
    window = MainWindow()
    qtbot.addWidget(window)
    _mock_login(mocker)
    resp = mocker.Mock()
    resp.status_code = 401
    resp.text = "Unauthorized"
    mocker.patch.object(window.session, "get", return_value=resp)

    window.login_username_input.setText("alice")
    window.login_password_input.setText("secret")
    window.authenticate()

    assert window.stacked_widget.currentWidget() is window.main_app_widget
    assert all(c.node.booked_by is None for c in window.channel_nodes.values())


def test_testing_mode_login_does_not_fetch_channels(qtbot, mocker):
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    mock_get = mocker.patch.object(window.session, "get")

    window.login_username_input.setText("alice")
    window.login_password_input.setText("secret")
    window.authenticate()

    mock_get.assert_not_called()


def _window_with_bookings(qtbot, mocker, bookings, user="alice"):
    """A MainWindow logged in as `user`, with channel bookings {channel: owner}."""
    mock_get = mocker.patch("requests.Session.get")
    resp = mocker.Mock()
    resp.status_code = 200
    resp.json.return_value = {"channels": [
        {"channel_number": ch, "status": "booked", "user_name": owner}
        for ch, owner in bookings.items()
    ]}
    mock_get.return_value = resp

    window = MainWindow()
    qtbot.addWidget(window)
    window.login_username = user
    window.fetch_booked_channels()
    return window


def test_release_sends_only_selected_own_channels(qtbot, mocker):
    """Release frees only the selected channels and never re-books the others."""
    window = _window_with_bookings(qtbot, mocker, {1: "alice", 2: "alice", 3: "alice", 4: "bob"})
    mock_post = mocker.patch("requests.Session.post")
    mock_post.return_value = mocker.Mock(status_code=200)

    # Your own bookings start selected; deselect 2 to keep it. Bob's channel 4
    # is ignored even if marked selected, because it is not yours.
    window.channel_nodes[2].node.is_active = False
    window.channel_nodes[4].node.is_active = True

    window.release_channels()

    assert mock_post.call_count == 1
    url = mock_post.call_args.args[0]
    assert url.endswith("/channels/release/alice")
    assert mock_post.call_args.kwargs["json"] == {"channel_numbers": [1, 3]}
    assert not any("/channels/book" in str(c.args[0]) for c in mock_post.call_args_list)


def test_release_with_no_own_channel_selected_sends_nothing(qtbot, mocker):
    window = _window_with_bookings(qtbot, mocker, {1: "alice", 2: "bob"})
    mock_post = mocker.patch("requests.Session.post")
    warn = mocker.patch("ui.main_window.QMessageBox.warning")
    window.channel_nodes[1].node.is_active = False
    window.channel_nodes[2].node.is_active = True

    window.release_channels()

    mock_post.assert_not_called()
    warn.assert_called_once()


def test_release_conflict_shows_backend_detail(qtbot, mocker):
    """A 409 from MaaS (channel not booked by you) is shown to the user."""
    window = _window_with_bookings(qtbot, mocker, {1: "alice"})
    resp = mocker.Mock(status_code=409, text="raw")
    resp.json.return_value = {"detail": "Cannot release channels [1] - not booked by alice"}
    mocker.patch("requests.Session.post", return_value=resp)
    warn = mocker.patch("ui.main_window.QMessageBox.warning")
    window.channel_nodes[1].node.is_active = True

    window.release_channels()

    assert "not booked by alice" in warn.call_args.args[2]
