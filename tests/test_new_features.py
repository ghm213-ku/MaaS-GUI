import pytest
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow

@pytest.fixture(autouse=True)
def mock_all_requests(mocker):
    mock_get = mocker.patch("requests.Session.get")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"channels": []}
    mock_get.return_value = mock_resp
    return mock_get

def test_login_positive(qtbot, mocker):
    mock_post = mocker.patch("requests.post")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"token": "fake-token"}
    mock_post.return_value = mock_resp
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    window.login_username_input.setText("testuser")
    window.login_password_input.setText("password123")
    
    # simulate click
    window.btn_login.click()
    
    assert window.auth_token == "fake-token"
    assert window.login_username == "testuser"
    assert window.stacked_widget.currentWidget() == window.main_app_widget

def test_login_negative_empty(qtbot, mocker):
    mocker.patch("ui.main_window.QMessageBox.warning")
    window = MainWindow()
    qtbot.addWidget(window)
    
    window.login_username_input.setText("")
    window.login_password_input.setText("")
    
    window.btn_login.click()
    import ui.main_window
    ui.main_window.QMessageBox.warning.assert_called_with(
        window, "Invalid Input", "User Name and Password cannot be empty."
    )
    assert window.stacked_widget.currentWidget() == window.login_widget

def test_change_password_positive(qtbot, mocker):
    mock_put = mocker.patch("requests.Session.put")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_put.return_value = mock_resp
    
    mocker.patch("ui.main_window.QMessageBox.information")
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # bypass login
    window.stacked_widget.setCurrentWidget(window.main_app_widget)
    
    window.old_password_input.setText("oldpass")
    window.new_password_input.setText("newpass")
    window.confirm_password_input.setText("newpass")
    
    window.btn_change_password.click()
    
    import ui.main_window
    ui.main_window.QMessageBox.information.assert_called_with(
        window, "Success", "Password updated successfully."
    )
    assert window.old_password_input.text() == ""
    assert window.new_password_input.text() == ""

def test_change_password_negative_mismatch(qtbot, mocker):
    mocker.patch("ui.main_window.QMessageBox.warning")
    window = MainWindow()
    qtbot.addWidget(window)
    
    window.old_password_input.setText("oldpass")
    window.new_password_input.setText("newpass")
    window.confirm_password_input.setText("wrongpass")
    
    window.btn_change_password.click()
    
    import ui.main_window
    ui.main_window.QMessageBox.warning.assert_called_with(
        window, "Error", "New passwords do not match."
    )
    assert window.new_password_input.text() == "newpass"

def test_histogram_mode_change(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Test Start-Stop mode (default)
    window.hist_mode_combo.setCurrentText("Start-Stop")
    assert not window.hist_n_values_input.isEnabled()
    assert window.hist_binwidth_input.isEnabled()
    
    # Test Histogram mode
    window.hist_mode_combo.setCurrentText("Histogram")
    assert window.hist_n_values_input.isEnabled()
    assert window.hist_binwidth_input.isEnabled()
    
    # Test Correlation mode
    window.hist_mode_combo.setCurrentText("Correlation")
    assert window.hist_n_values_input.isEnabled()
    assert window.hist_binwidth_input.isEnabled()

def test_start_histogram_negative_no_channels(qtbot, mocker):
    mocker.patch("ui.main_window.QMessageBox.warning")
    window = MainWindow()
    qtbot.addWidget(window)
    
    window.hist_binwidth_input.setText("invalid")
    window.hist_n_values_input.setText("100")
    window.hist_mode_combo.setCurrentText("Histogram")
    window.hist_btn_play_pause.click()
    import ui.main_window
    ui.main_window.QMessageBox.warning.assert_called_with(
        window, "Invalid Input", "Please enter valid numbers for Binwidth and n_values."
    )

def test_export_histogram_negative_no_data(qtbot, mocker):
    mocker.patch("ui.main_window.QMessageBox.warning")
    window = MainWindow()
    qtbot.addWidget(window)
    
    window.hist_data_buffer = None # Mock initialization since __init__ doesn't do it
    window.hist_btn_export.setEnabled(True)
    window.hist_btn_export.click()
    
    import ui.main_window
    ui.main_window.QMessageBox.warning.assert_called_with(
        window, "No Data", "There is no data to export."
    )


def test_coincidences_tab_boxes_add_remove(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Check default 1 box
    assert len(window.coinc_boxes) == 1
    assert len(window.coinc_combos) == 1
    
    # Click + button to add boxes
    window.coinc_btn_add.click()
    assert len(window.coinc_boxes) == 2
    
    window.coinc_btn_add.click()
    assert len(window.coinc_boxes) == 3
    
    # Click - button to remove boxes
    window.coinc_btn_remove.click()
    assert len(window.coinc_boxes) == 2

    window.coinc_btn_remove.click()
    assert len(window.coinc_boxes) == 1

    # Should not remove below 1 box
    window.coinc_btn_remove.click()
    assert len(window.coinc_boxes) == 1


def test_coincidences_tab_validation_format_and_empty(qtbot, mocker):
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]
    mock_warn = mocker.patch('PyQt6.QtWidgets.QMessageBox.warning')

    # 1. Empty box validation
    window.coinc_boxes[0].setText('')
    window.start_coincidences_measurement()
    assert mock_warn.called
    assert window.coinc_worker is None

    # 2. Non-integer format validation
    mock_warn.reset_mock()
    window.coinc_boxes[0].setText('1, abc')
    window.start_coincidences_measurement()
    assert mock_warn.called
    assert 'Invalid Format' in mock_warn.call_args[0][1]
    assert window.coinc_worker is None

    # 3. Single channel validation (< 2 channels)
    mock_warn.reset_mock()
    window.coinc_boxes[0].setText('1')
    window.start_coincidences_measurement()
    assert mock_warn.called
    assert 'at least 2 channels' in mock_warn.call_args[0][2].lower()
    assert window.coinc_worker is None

    # 4. Duplicate channels within group validation
    mock_warn.reset_mock()
    window.coinc_boxes[0].setText('1, 1')
    window.start_coincidences_measurement()
    assert mock_warn.called
    assert 'duplicate' in mock_warn.call_args[0][2].lower()
    assert window.coinc_worker is None


def test_coincidences_tab_validation_unselected_channels(qtbot, mocker):
    window = MainWindow()
    qtbot.addWidget(window)
    # User chose channels 1 and 2 in the beginning
    window.get_selected_channels = lambda: [1, 2]
    mock_warn = mocker.patch('PyQt6.QtWidgets.QMessageBox.warning')

    # Box contains channel 3 which was not chosen in the beginning
    window.coinc_boxes[0].setText('1, 3')
    window.start_coincidences_measurement()
    assert mock_warn.called
    assert 'Channel Not Selected' in mock_warn.call_args[0][1]
    assert 'not chosen' in mock_warn.call_args[0][2].lower()
    assert window.coinc_worker is None


def test_coincidences_tab_validation_success_and_multi_group(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.force_mock = True
    window.get_selected_channels = lambda: [1, 2, 3, 4]

    # Group 1: 1, 2, 3
    window.coinc_boxes[0].setText('1, 2, 3')

    # Group 2: 2, 4
    window.coinc_btn_add.click()
    assert len(window.coinc_boxes) == 2
    window.coinc_boxes[1].setText('2, 4')

    window.start_coincidences_measurement()
    assert window.coinc_worker is not None
    assert window.coinc_worker.coincidences == [[1, 2, 3], [2, 4]]
    assert window.coinc_worker.channels == [1, 2, 3, 4]

    window.coinc_worker.stop()
    window.coinc_worker.wait(1000)
