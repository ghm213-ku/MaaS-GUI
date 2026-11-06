import pytest
import json
import base64
from unittest.mock import Mock
from ui.main_window import MainWindow

# MainWindow fetches channels from MaaS on creation; never hit a live backend.
pytestmark = pytest.mark.usefixtures("mock_maas_channels")


def create_mock_jwt(role="admin", user_id=1):
    payload = json.dumps({"sub": user_id, "role": role})
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.{b64}.fake_signature"


def test_decode_jwt_token(qtbot):
    """Verify JWT token payload decoding without external libraries."""
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    
    # Valid admin token
    admin_jwt = create_mock_jwt(role="admin", user_id=42)
    decoded = window.decode_jwt_token(admin_jwt)
    assert decoded["sub"] == 42
    assert decoded["role"] == "admin"

    # Valid operator token
    op_jwt = create_mock_jwt(role="operator", user_id=10)
    decoded_op = window.decode_jwt_token(op_jwt)
    assert decoded_op["role"] == "operator"

    # Invalid / empty tokens
    assert window.decode_jwt_token("") == {}
    assert window.decode_jwt_token("not.a.valid.jwt.string.at.all") == {}
    assert window.decode_jwt_token(None) == {}


def test_admin_login_adds_add_user_tab(qtbot, mocker):
    """When an admin logs in, the 'User Management' tab is dynamically added to the tab widget."""
    window = MainWindow()
    qtbot.addWidget(window)

    # Initial tabs: Channels Setup, Counter, Histograms, Coincidences, Account
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
    assert hasattr(window, "new_user_username_input")
    assert hasattr(window, "new_user_role_combo")


def test_non_admin_login_does_not_add_add_user_tab(qtbot, mocker):
    """When a non-admin (e.g. operator) logs in, the 'User Management' tab is NOT added."""
    window = MainWindow()
    qtbot.addWidget(window)

    operator_token = create_mock_jwt(role="operator")
    mock_post = mocker.patch("requests.post")
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"token": operator_token, "expires_in": 3600}
    mock_post.return_value = mock_resp

    window.login_username_input.setText("operator_user")
    window.login_password_input.setText("pass123")
    window.authenticate()

    tab_names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert "User Management" not in tab_names
    assert window.user_role == "operator"


def test_mock_mode_admin_login(qtbot):
    """In mock mode with admin username, 'User Management' tab is added."""
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)

    window.login_username_input.setText("admin")
    window.login_password_input.setText("admin")
    window.authenticate()

    tab_names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert "User Management" in tab_names
    assert window.user_role == "admin"


def test_add_user_tab_lists_user_types(qtbot):
    """The 'Add user' tab lists both user types: Operator and Viewer."""
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    window.build_add_user_tab()

    items = [window.new_user_role_combo.itemText(i) for i in range(window.new_user_role_combo.count())]
    assert "Operator" in items
    assert "Viewer" in items
    assert window.new_user_role_combo.findText("Operator") >= 0
    assert window.new_user_role_combo.findText("Viewer") >= 0


def test_submit_add_user_empty_username_shows_warning(qtbot, mocker):
    """Attempting to submit without a username shows a warning."""
    window = MainWindow(force_mock=True)
    qtbot.addWidget(window)
    window.build_add_user_tab()

    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")
    window.new_user_username_input.setText("")
    window.submit_add_user()

    assert mock_warn.called
    assert "Username cannot be empty" in mock_warn.call_args[0][2]


def test_submit_add_user_calls_maas_api_success(qtbot, mocker):
    """Submitting valid user calls MaaS /auth/users and shows success."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.auth_token = create_mock_jwt(role="admin")
    window.build_add_user_tab()

    mock_post = mocker.patch.object(window.session, "post")
    mock_resp = Mock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"message": "User created successfully", "user_id": 5}
    mock_post.return_value = mock_resp

    mock_info = mocker.patch("PyQt6.QtWidgets.QMessageBox.information")

    window.new_user_username_input.setText("test_operator")
    # Select Operator
    op_idx = window.new_user_role_combo.findText("Operator")
    window.new_user_role_combo.setCurrentIndex(op_idx)

    window.submit_add_user()

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert f"{window.server_url}/auth/users" in args[0]
    assert kwargs["json"]["username"] == "test_operator"
    assert kwargs["json"]["role_id"] == 2
    assert kwargs["headers"]["Authorization"] == f"Bearer {window.auth_token}"

    assert mock_info.called
    assert "created successfully" in mock_info.call_args[0][2]
    # Username input should be cleared on success
    assert window.new_user_username_input.text() == ""


def test_submit_add_user_duplicate_error(qtbot, mocker):
    """Backend returning 400 duplicate username error is displayed to user."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.auth_token = create_mock_jwt(role="admin")
    window.build_add_user_tab()

    mock_post = mocker.patch.object(window.session, "post")
    mock_resp = Mock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"detail": "Username already exists or invalid role"}
    mock_post.return_value = mock_resp

    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.new_user_username_input.setText("existing_user")
    window.submit_add_user()

    assert mock_warn.called
    assert "Username already exists" in mock_warn.call_args[0][2]
