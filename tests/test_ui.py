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
