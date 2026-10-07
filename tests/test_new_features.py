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
    mock_post = mocker.patch("requests.Session.post")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp
    
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


def test_coincidences_tab_positive(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Check initial state
    window.get_selected_channels = lambda: [1, 2, 3, 4, 5]
    assert len(window.coinc_combos) == 2
    
    # Click + button
    window.coinc_btn_add.click()
    assert len(window.coinc_combos) == 3
    
    # Click + button again
    window.coinc_btn_add.click()
    assert len(window.coinc_combos) == 4
    
    # Click - button
    window.coinc_btn_remove.click()
    assert len(window.coinc_combos) == 3

def test_coincidences_tab_negative(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Check initial state
    assert len(window.coinc_combos) == 2
    
    # Click - button, should not remove below 2
    window.coinc_btn_remove.click()
    assert len(window.coinc_combos) == 2
    
    window.coinc_btn_remove.click()
    assert len(window.coinc_combos) == 2
