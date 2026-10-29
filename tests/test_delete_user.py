import pytest
import json
import base64
from unittest.mock import Mock
from PyQt6.QtWidgets import QMessageBox
from ui.main_window import MainWindow


def create_mock_jwt(role="admin", user_id=1):
    payload = json.dumps({"sub": user_id, "role": role})
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.{b64}.fake_signature"


def test_admin_login_adds_user_management_tab(qtbot, mocker):
    """When an admin logs in, 'User Management' tab is dynamically added."""
    window = MainWindow()
    qtbot.addWidget(window)

    # Initial tabs should not have User Management
    tab_names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert "User Management" not in tab_names

    # Mock login returning admin JWT
    admin_token = create_mock_jwt(role="admin")
    mock_post = mocker.patch("requests.post")
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"token": admin_token, "expires_in": 3600}
    mock_post.return_value = mock_resp

    window.login_username_input.setText("admin")
    window.login_password_input.setText("admin123")
    window.authenticate()

    # Tab should now be present
    tab_names_after = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert "User Management" in tab_names_after
    assert window.user_role == "admin"
    assert hasattr(window, "user_mgmt_action_combo")
    assert hasattr(window, "delete_user_username_input")
    assert hasattr(window, "btn_delete_user")
    assert hasattr(window, "reset_pwd_username_input")
    assert hasattr(window, "btn_reset_user_password")


def test_user_management_dropdown_switching(qtbot):
    """Dropdown switches between Add User, Delete User, and Change User Password."""
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    window.build_user_management_tab()

    # Default is Add User (index 0)
    assert window.user_mgmt_action_combo.currentIndex() == 0
    assert window.user_mgmt_stack.currentIndex() == 0

    # Switch to Delete User (index 1)
    window.user_mgmt_action_combo.setCurrentIndex(1)
    assert window.user_mgmt_stack.currentIndex() == 1

    # Switch to Change User Password (index 2)
    window.user_mgmt_action_combo.setCurrentIndex(2)
    assert window.user_mgmt_stack.currentIndex() == 2


def test_submit_delete_user_empty_username_shows_warning(qtbot, mocker):
    """Attempting to submit delete with empty username shows a warning."""
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    window.build_user_management_tab()

    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")
    window.delete_user_username_input.setText("")
    window.submit_delete_user()

    assert mock_warn.called
    assert "Username cannot be empty" in mock_warn.call_args[0][2]


def test_submit_delete_user_self_deletion_prohibited(qtbot, mocker):
    """Admin cannot delete their own account."""
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    window.login_username = "admin"
    window.build_user_management_tab()

    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")
    window.delete_user_username_input.setText("admin")
    window.submit_delete_user()

    assert mock_warn.called
    assert "cannot delete your own" in mock_warn.call_args[0][2]


def test_submit_delete_user_cancelled_by_user(qtbot, mocker):
    """When user rejects confirmation question, no DELETE request is sent."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.login_username = "admin"
    window.auth_token = create_mock_jwt(role="admin")
    window.build_user_management_tab()

    mock_quest = mocker.patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.No)
    mock_delete = mocker.patch.object(window.session, "delete")

    window.delete_user_username_input.setText("test_target")
    window.submit_delete_user()

    assert mock_quest.called
    assert not mock_delete.called


def test_submit_delete_user_calls_maas_api_success(qtbot, mocker):
    """Confirmed deletion calls DELETE /auth/users/{username} and clears input."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.login_username = "admin"
    window.auth_token = create_mock_jwt(role="admin")
    window.build_user_management_tab()

    mocker.patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
    mock_delete = mocker.patch.object(window.session, "delete")
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": "User deleted successfully"}
    mock_delete.return_value = mock_resp

    mock_info = mocker.patch("PyQt6.QtWidgets.QMessageBox.information")

    window.delete_user_username_input.setText("old_operator")
    window.submit_delete_user()

    mock_delete.assert_called_once()
    args, kwargs = mock_delete.call_args
    assert "http://127.0.0.1:8000/auth/users/old_operator" in args[0]
    assert kwargs["headers"]["Authorization"] == f"Bearer {window.auth_token}"

    assert mock_info.called
    assert "deleted successfully" in mock_info.call_args[0][2]
    assert window.delete_user_username_input.text() == ""


def test_submit_delete_user_not_found(qtbot, mocker):
    """Backend returning 404 User not found displays appropriate message."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.login_username = "admin"
    window.auth_token = create_mock_jwt(role="admin")
    window.build_user_management_tab()

    mocker.patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
    mock_delete = mocker.patch.object(window.session, "delete")
    mock_resp = Mock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"detail": "User not found"}
    mock_delete.return_value = mock_resp

    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.delete_user_username_input.setText("nonexistent_user")
    window.submit_delete_user()

    assert mock_warn.called
    assert "User not found" in mock_warn.call_args[0][2]


def test_submit_delete_user_mock_mode(qtbot, mocker):
    """In force_mock mode, deletion succeeds without backend call."""
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    window.login_username = "admin"
    window.build_user_management_tab()

    mocker.patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
    mock_info = mocker.patch("PyQt6.QtWidgets.QMessageBox.information")

    window.delete_user_username_input.setText("mock_user_to_delete")
    window.submit_delete_user()

    assert mock_info.called
    assert "deleted successfully" in mock_info.call_args[0][2]
    assert window.delete_user_username_input.text() == ""


# --- Change User Password Tests ---

def test_submit_reset_password_empty_fields_shows_warning(qtbot, mocker):
    """Attempting to submit reset password with empty fields shows warning."""
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    window.build_user_management_tab()

    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")
    window.reset_pwd_username_input.setText("")
    window.submit_reset_password()

    assert mock_warn.called
    assert "Username cannot be empty" in mock_warn.call_args[0][2]


def test_submit_reset_password_mismatch_shows_warning(qtbot, mocker):
    """Mismatch in new and confirm password shows warning."""
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    window.build_user_management_tab()

    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")
    window.reset_pwd_username_input.setText("testuser")
    window.reset_pwd_new_password_input.setText("newpass123")
    window.reset_pwd_confirm_password_input.setText("different123")
    window.submit_reset_password()

    assert mock_warn.called
    assert "passwords do not match" in mock_warn.call_args[0][2].lower()


def test_submit_reset_password_calls_maas_api_success(qtbot, mocker):
    """Admin resetting user password sends PUT /auth/users/{username}/password."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.auth_token = create_mock_jwt(role="admin")
    window.build_user_management_tab()

    mocker.patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
    mock_put = mocker.patch.object(window.session, "put")
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": "Password updated successfully"}
    mock_put.return_value = mock_resp

    mock_info = mocker.patch("PyQt6.QtWidgets.QMessageBox.information")

    window.reset_pwd_username_input.setText("sushantyadav")
    window.reset_pwd_new_password_input.setText("newsecurepass")
    window.reset_pwd_confirm_password_input.setText("newsecurepass")
    window.submit_reset_password()

    mock_put.assert_called_once()
    args, kwargs = mock_put.call_args
    assert "http://127.0.0.1:8000/auth/users/sushantyadav/password" in args[0]
    assert kwargs["json"]["new_password"] == "newsecurepass"
    assert kwargs["headers"]["Authorization"] == f"Bearer {window.auth_token}"

    assert mock_info.called
    assert "changed successfully" in mock_info.call_args[0][2]
    assert window.reset_pwd_username_input.text() == ""
    assert window.reset_pwd_new_password_input.text() == ""
    assert window.reset_pwd_confirm_password_input.text() == ""


def test_submit_reset_password_user_not_found(qtbot, mocker):
    """Admin resetting non-existent user shows 404 warning."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.auth_token = create_mock_jwt(role="admin")
    window.build_user_management_tab()

    mocker.patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
    mock_put = mocker.patch.object(window.session, "put")
    mock_resp = Mock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"detail": "User not found"}
    mock_put.return_value = mock_resp

    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.reset_pwd_username_input.setText("ghost_user")
    window.reset_pwd_new_password_input.setText("pass")
    window.reset_pwd_confirm_password_input.setText("pass")
    window.submit_reset_password()

    assert mock_warn.called
    assert "User not found" in mock_warn.call_args[0][2]
