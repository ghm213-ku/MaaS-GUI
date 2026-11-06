import numpy as np
import requests
import json
import base64
import logging
import os

logger = logging.getLogger(__name__)

# pyrefly: ignore [missing-import]
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidgetAction,
    QMenu,QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QMessageBox,
                             QTabWidget, QGridLayout, QScrollArea, QCheckBox,
                             QFrame, QLineEdit, QDialog, QFormLayout, QSizePolicy, QComboBox, QStackedWidget)
from PyQt6.QtGui import QDoubleValidator, QIntValidator
from PyQt6.QtCore import Qt, pyqtSignal

from hardware.worker import CountRateWorker, normalize_server_url
from hardware.histogram_worker import HistogramWorker
from hardware.coincidences_worker import CoincidencesWorker

class ChannelConfigPopup(QDialog):
    def __init__(self, current_trigger, current_delay, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("QDialog { background-color: white; border: 1px solid black; border-radius: 5px; }")
        
        layout = QFormLayout(self)
        
        self.trigger_input = QLineEdit(str(current_trigger))
        self.delay_input = QLineEdit(str(current_delay))
        
        self.btn_save = QPushButton("Save")
        self.btn_save.setAutoDefault(False)
        self.btn_save.setDefault(False)
        self.btn_save.clicked.connect(self.accept)
        
        # Pressing Enter on Trigger moves focus to Delay
        self.trigger_input.returnPressed.connect(self.delay_input.setFocus)
        # Pressing Enter on Delay saves and closes
        self.delay_input.returnPressed.connect(self.accept)
        
        layout.addRow("Trigger (V):", self.trigger_input)
        layout.addRow("Delay (ps):", self.delay_input)
        layout.addRow(self.btn_save)

    def get_values(self):
        try:
            # Replace comma with dot for locales that use comma decimals
            t_str = self.trigger_input.text().replace(',', '.')
            t = float(t_str)
        except ValueError:
            t = 0.5
        try:
            d = int(self.delay_input.text())
        except ValueError:
            d = 0
        return t, d

class ChannelNodeWidget(QFrame):
    toggled = pyqtSignal(int, bool)
    
    def __init__(self, channel_id, parent=None):
        super().__init__(parent)
        self.channel_id = channel_id
        self.is_active = False
        self.booked_by = None
        self.is_current_user = False
        
        self.trigger_val = 0.5
        self.delay_val = 0
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_trig = QLabel(f"{self.trigger_val}V")
        self.lbl_trig.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_trig.setStyleSheet("font-family: 'Segoe UI', Arial; font-size: 9px; border: none; background: transparent; color: #555;")
        
        self.lbl_dly = QLabel(f"{self.delay_val}ps")
        self.lbl_dly.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_dly.setStyleSheet("font-family: 'Segoe UI', Arial; font-size: 9px; border: none; background: transparent; color: #555;")
        
        self.layout.addWidget(self.lbl_trig)
        self.layout.addWidget(self.lbl_dly)
        
        self.update_style()
        
    def open_settings(self):
        popup = ChannelConfigPopup(self.trigger_val, self.delay_val, self.window())
        from PyQt6.QtGui import QCursor
        popup.move(QCursor.pos())
        if popup.exec() == QDialog.DialogCode.Accepted:
            t, d = popup.get_values()
            self.trigger_val = t
            self.delay_val = d
            self.lbl_trig.setText(f"{t}V")
            self.lbl_dly.setText(f"{d}ps")
            
    def set_booked_by(self, user_name, is_current_user):
        self.booked_by = user_name
        self.is_current_user = is_current_user
        
        if not user_name:
            self.is_active = False
            self.lbl_trig.show()
            self.lbl_dly.show()
            self.setToolTip("")
        else:
            if is_current_user:
                self.is_active = True
                self.lbl_trig.show()
                self.lbl_dly.show()
            else:
                self.is_active = False
                self.lbl_trig.hide()
                self.lbl_dly.hide()
            self.setToolTip(f"Booked by: {user_name}")
            
        self.update_style()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Dynamically scale font size with width, min 9px
        font_size = max(9, int(self.width() * 0.16))
        self.lbl_trig.setStyleSheet(f"font-family: 'Segoe UI', Arial; font-size: {font_size}px; border: none; background: transparent; color: #555;")
        self.lbl_dly.setStyleSheet(f"font-family: 'Segoe UI', Arial; font-size: {font_size}px; border: none; background: transparent; color: #555;")
        self.update_style()
        
    def update_style(self):
        radius = self.width() // 2
        if self.booked_by and not self.is_current_user:
            self.setStyleSheet(f"""
                ChannelNodeWidget {{
                    background-color: #d3d3d3;
                    border: 1px solid #a9a9a9;
                    border-radius: {radius}px;
                }}
            """)
        elif self.is_active:
            self.setStyleSheet(f"""
                ChannelNodeWidget {{
                    background-color: #e3f2fd;
                    border: 1px solid #90caf9;
                    border-radius: {radius}px;
                }}
            """)
        elif self.booked_by and self.is_current_user:
            self.setStyleSheet(f"""
                ChannelNodeWidget {{
                    background-color: #e8f5e9;
                    border: 1px solid #4caf50;
                    border-radius: {radius}px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ChannelNodeWidget {{
                    background-color: #f9f9f9;
                    border: 1px solid #e0e0e0;
                    border-radius: {radius}px;
                }}
            """)
            
    def mousePressEvent(self, event):
        if self.booked_by and not self.is_current_user:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self.is_active = not self.is_active
            self.update_style()
            self.toggled.emit(self.channel_id, self.is_active)
        elif event.button() == Qt.MouseButton.RightButton:
            self.open_settings()
        super().mousePressEvent(event)

class ChannelNodeContainer(QWidget):
    def __init__(self, channel_id, parent=None):
        super().__init__(parent)
        self.full_user_name = ""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        
        self.node = ChannelNodeWidget(channel_id, self)
        
        self.lbl_user = QLabel(" ")
        self.lbl_user.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_user.setFixedHeight(12)
        
        self.layout.addStretch()
        self.layout.addWidget(self.node, 0, Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_user, 0, Qt.AlignmentFlag.AlignCenter)
        self.layout.addStretch()
        
    def set_booked_by(self, user_name, is_current_user):
        self.node.set_booked_by(user_name, is_current_user)
        self.full_user_name = user_name
        
        # Keep text dark grey regardless of user
        self.lbl_user.setStyleSheet("font-family: 'Segoe UI', Arial; font-size: 10px; font-weight: bold; color: #555;")
        self.update_elided_text()
        
    def update_elided_text(self):
        if not self.full_user_name:
            self.lbl_user.setText(" ")
            return
            
        # The container width represents the total horizontal space for this cell
        available_width = self.width() - 8
        if available_width < 10:
            return
            
        metrics = self.lbl_user.fontMetrics()
        elided = metrics.elidedText(self.full_user_name, Qt.TextElideMode.ElideRight, available_width)
        self.lbl_user.setText(elided)
        
    def resizeEvent(self, event):
        side = min(self.width(), self.height()) - 4
        side -= self.lbl_user.height()
        side = max(40, min(side, 120))
        self.node.setFixedSize(side, side)
        super().resizeEvent(event)
        self.update_elided_text()


from PyQt6.QtWidgets import QStyle

class SITimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        strings = []
        for value in values:
            if value == 0:
                strings.append("0")
                continue
            
            prefixes = [('y', 1e-24), ('z', 1e-21), ('a', 1e-18), ('f', 1e-15), 
                        ('p', 1e-12), ('n', 1e-9), ('µ', 1e-6), ('m', 1e-3),
                        ('', 1.0), ('k', 1e3), ('M', 1e6), ('G', 1e9)]
            
            abs_val = abs(value)
            formatted = f"{value:g}"
            for prefix, multiplier in reversed(prefixes):
                if abs_val >= multiplier * 0.999:
                    val = value / multiplier
                    formatted = f"{val:g}{prefix}"
                    break
            
            strings.append(formatted)
        return strings


class MainWindow(QMainWindow):
    def __init__(self, force_mock=False, server_ip=None):
        super().__init__()
        self.force_mock = force_mock

        if server_ip is None:
            server_ip = os.environ.get("MAAS_IP", os.environ.get("MAAS_HOST", "127.0.0.1"))
        self.server_ip = str(server_ip).strip() if server_ip else "127.0.0.1"
        self.server_url, self.ws_server_url = normalize_server_url(self.server_ip)
        self.api_url = f"{self.server_url}/api/v1"
        self.ws_api_url = f"{self.ws_server_url}/api/v1"
        
        self.auth_token = ""
        self.login_username = ""
        self.user_role = ""
        self.jwt_payload = {}
        self.add_user_tab = None
        
        self.setWindowTitle("Swabian Count Rate Monitor")
        self.resize(260, 220)
        self.worker = None
        self.old_workers = []
        self.session = requests.Session()
        
        self.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTabWidget::pane {
                border: none;
                border-top: 1px solid #eaeaea;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #ffffff;
                color: #888888;
                padding: 10px 20px;
                border: none;
                font-size: 13px;
                font-weight: 500;
            }
            QTabBar::tab:hover {
                color: #333333;
            }
            QTabBar::tab:selected {
                color: #111111;
                border-bottom: 2px solid #111111;
            }
            QPushButton {
                background-color: #fbfbfb;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px 12px;
                color: #333333;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
            QPushButton:pressed, QPushButton:checked {
                background-color: #e8e8e8;
                border-color: #d0d0d0;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        self.build_login_screen()
        self.build_main_app()
        
        self.stacked_widget.addWidget(self.login_widget)
        self.stacked_widget.addWidget(self.main_app_widget)
        self.stacked_widget.setCurrentWidget(self.login_widget)


    def set_server_ip(self, ip_address: str):
        if not ip_address or not str(ip_address).strip():
            ip_address = "127.0.0.1"
        self.server_ip = str(ip_address).strip()
        self.server_url, self.ws_server_url = normalize_server_url(self.server_ip)
        self.api_url = f"{self.server_url}/api/v1"
        self.ws_api_url = f"{self.ws_server_url}/api/v1"
        if hasattr(self, 'login_server_ip_input') and self.login_server_ip_input.text() != self.server_ip:
            self.login_server_ip_input.setText(self.server_ip)
        if hasattr(self, 'account_server_ip_input') and self.account_server_ip_input.text() != self.server_ip:
            self.account_server_ip_input.setText(self.server_ip)

    def build_login_screen(self):
        self.login_widget = QWidget()
        layout = QVBoxLayout(self.login_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)
        
        lbl_title = QLabel("Login")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 8px;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        self.login_username_input = QLineEdit()
        self.login_username_input.setPlaceholderText("Username")
        self.login_username_input.setFixedWidth(180)
        self.login_username_input.setStyleSheet("padding: 4px; border: 1px solid #ccc; border-radius: 2px;")
        
        self.login_password_input = QLineEdit()
        self.login_password_input.setPlaceholderText("Password")
        self.login_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_password_input.setFixedWidth(180)
        self.login_password_input.setStyleSheet("padding: 4px; border: 1px solid #ccc; border-radius: 2px;")

        self.login_server_ip_input = QLineEdit(getattr(self, 'server_ip', '127.0.0.1'))
        self.login_server_ip_input.setPlaceholderText("MaaS IP (e.g. 192.168.1.100)")
        self.login_server_ip_input.setFixedWidth(180)
        self.login_server_ip_input.setStyleSheet("padding: 4px; border: 1px solid #ccc; border-radius: 2px;")
        self.server_ip_input = self.login_server_ip_input
        
        self.btn_login = QPushButton("Login")
        self.btn_login.setFixedWidth(180)
        self.btn_login.setStyleSheet("QPushButton { background-color: #111111; color: white; padding: 4px; border-radius: 2px; } QPushButton:hover { background-color: #333333; }")
        
        self.btn_login.setDefault(True)
        self.btn_login.setAutoDefault(True)
        self.login_username_input.returnPressed.connect(self.login_password_input.setFocus)
        self.login_password_input.returnPressed.connect(self.login_server_ip_input.setFocus)
        self.login_server_ip_input.returnPressed.connect(self.btn_login.click)
        self.btn_login.clicked.connect(self.authenticate)
        
        layout.addWidget(self.login_username_input, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.login_password_input, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.login_server_ip_input, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.btn_login, alignment=Qt.AlignmentFlag.AlignHCenter)

    def decode_jwt_token(self, token: str) -> dict:
        if not token or not isinstance(token, str):
            return {}
        try:
            clean_token = token.strip().strip('"').strip("'")
            parts = clean_token.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                padded = payload_b64 + "=" * (-len(payload_b64) % 4)
                decoded_bytes = base64.urlsafe_b64decode(padded)
                return json.loads(decoded_bytes.decode("utf-8"))
        except Exception as e:
            logger.debug(f"Failed to decode JWT token: {e}")
        return {}

    def update_admin_tab_visibility(self):
        user_mgmt_tab_index = -1
        tabs_to_remove = []
        for i in range(self.tabs.count()):
            text = self.tabs.tabText(i).strip().lower()
            if text in ["user management", "add user", "delete user"]:
                if user_mgmt_tab_index == -1 and text == "user management":
                    user_mgmt_tab_index = i
                else:
                    tabs_to_remove.append(i)

        # Remove any legacy or duplicate tabs
        for idx in sorted(tabs_to_remove, reverse=True):
            self.tabs.removeTab(idx)

        is_admin = getattr(self, 'user_role', '').lower() == "admin"
        if is_admin:
            if user_mgmt_tab_index == -1:
                if not hasattr(self, 'user_mgmt_tab') or self.user_mgmt_tab is None:
                    self.build_user_management_tab()
                self.tabs.addTab(self.user_mgmt_tab, "User Management")
        else:
            if user_mgmt_tab_index != -1:
                self.tabs.removeTab(user_mgmt_tab_index)

    def build_user_management_tab(self):
        self.user_mgmt_tab = QWidget()
        self.user_management_tab = self.user_mgmt_tab
        self.add_user_tab = self.user_mgmt_tab
        self.delete_user_tab = self.user_mgmt_tab

        main_layout = QVBoxLayout(self.user_mgmt_tab)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(16)

        title = QLabel("User Management")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 2px;")
        main_layout.addWidget(title)

        subtitle = QLabel("Administrator portal to register new users, delete existing accounts, or reset user passwords.")
        subtitle.setStyleSheet("color: #666666; font-size: 12px; margin-bottom: 8px;")
        main_layout.addWidget(subtitle)

        # Dropdown selection for operation
        action_layout = QHBoxLayout()
        action_label = QLabel("Select Operation:")
        action_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        action_layout.addWidget(action_label)

        self.user_mgmt_action_combo = QComboBox()
        self.user_mgmt_action_combo.setFixedWidth(240)
        self.user_mgmt_action_combo.setStyleSheet("padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; font-weight: 500;")
        self.user_mgmt_action_combo.addItem("Add User")
        self.user_mgmt_action_combo.addItem("Delete User")
        self.user_mgmt_action_combo.addItem("Change User Password")
        action_layout.addWidget(self.user_mgmt_action_combo)
        action_layout.addStretch()
        main_layout.addLayout(action_layout)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("color: #e0e0e0; margin-top: 4px; margin-bottom: 4px;")
        main_layout.addWidget(sep)

        # Stacked widget for the 3 operations
        self.user_mgmt_stack = QStackedWidget()
        main_layout.addWidget(self.user_mgmt_stack)

        # ---- 1. Add User Widget ----
        self.add_user_widget = QWidget()
        add_layout = QVBoxLayout(self.add_user_widget)
        add_layout.setContentsMargins(0, 8, 0, 0)
        add_layout.setSpacing(12)

        add_desc = QLabel("Register a new user in MaaS. The initial password defaults to the username.")
        add_desc.setStyleSheet("color: #555555; font-size: 12px;")
        add_layout.addWidget(add_desc)

        add_form = QFormLayout()
        add_form.setSpacing(14)

        self.new_user_username_input = QLineEdit()
        self.new_user_username_input.setPlaceholderText("Enter username")
        self.new_user_username_input.setFixedWidth(240)
        self.new_user_username_input.setStyleSheet("padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px;")
        add_form.addRow("Username:", self.new_user_username_input)

        self.new_user_role_combo = QComboBox()
        self.new_user_role_combo.setFixedWidth(240)
        self.new_user_role_combo.setStyleSheet("padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px;")
        self.user_types = ["Operator", "Viewer"]
        self.role_id_map = {
            "Operator": 2,
            "Viewer": 3,
            "Admin": 1,
            "operator": 2,
            "viewer": 3,
            "admin": 1
        }
        self.new_user_role_combo.addItem("Operator", 2)
        self.new_user_role_combo.addItem("Viewer", 3)
        self.new_user_role_combo.addItem("Admin", 1)
        add_form.addRow("User Type:", self.new_user_role_combo)
        add_layout.addLayout(add_form)

        self.btn_create_user = QPushButton("Add User")
        self.btn_add_user = self.btn_create_user  # Alias
        self.btn_create_user.setFixedWidth(240)
        self.btn_create_user.setStyleSheet(
            "QPushButton { background-color: #111111; color: white; padding: 8px; font-weight: bold; border-radius: 4px; } "
            "QPushButton:hover { background-color: #333333; }"
        )
        self.btn_create_user.clicked.connect(self.submit_add_user)
        self.new_user_username_input.returnPressed.connect(self.submit_add_user)
        add_layout.addWidget(self.btn_create_user)

        self.add_user_status_label = QLabel("")
        self.add_user_status_label.setStyleSheet("font-size: 13px; font-weight: 500; margin-top: 4px;")
        add_layout.addWidget(self.add_user_status_label)
        add_layout.addStretch()

        self.user_mgmt_stack.addWidget(self.add_user_widget)

        # ---- 2. Delete User Widget ----
        self.delete_user_widget = QWidget()
        del_layout = QVBoxLayout(self.delete_user_widget)
        del_layout.setContentsMargins(0, 8, 0, 0)
        del_layout.setSpacing(12)

        del_desc = QLabel("Permanently delete an existing user account from MaaS.")
        del_desc.setStyleSheet("color: #555555; font-size: 12px;")
        del_layout.addWidget(del_desc)

        del_form = QFormLayout()
        del_form.setSpacing(14)

        self.delete_user_username_input = QLineEdit()
        self.delete_user_username_input.setPlaceholderText("Enter username to delete")
        self.delete_user_username_input.setFixedWidth(240)
        self.delete_user_username_input.setStyleSheet("padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px;")
        del_form.addRow("Username:", self.delete_user_username_input)
        del_layout.addLayout(del_form)

        self.btn_delete_user = QPushButton("Delete User")
        self.btn_remove_user = self.btn_delete_user  # Alias
        self.btn_delete_user.setFixedWidth(240)
        self.btn_delete_user.setStyleSheet(
            "QPushButton { background-color: #d32f2f; color: white; padding: 8px; font-weight: bold; border-radius: 4px; } "
            "QPushButton:hover { background-color: #b71c1c; }"
        )
        self.btn_delete_user.clicked.connect(self.submit_delete_user)
        self.delete_user_username_input.returnPressed.connect(self.submit_delete_user)
        del_layout.addWidget(self.btn_delete_user)

        self.delete_user_status_label = QLabel("")
        self.delete_user_status_label.setStyleSheet("font-size: 13px; font-weight: 500; margin-top: 4px;")
        del_layout.addWidget(self.delete_user_status_label)
        del_layout.addStretch()

        self.user_mgmt_stack.addWidget(self.delete_user_widget)

        # ---- 3. Change User Password Widget ----
        self.reset_pwd_widget = QWidget()
        pwd_layout = QVBoxLayout(self.reset_pwd_widget)
        pwd_layout.setContentsMargins(0, 8, 0, 0)
        pwd_layout.setSpacing(12)

        pwd_desc = QLabel("Reset password for any user account without needing their current password.")
        pwd_desc.setStyleSheet("color: #555555; font-size: 12px;")
        pwd_layout.addWidget(pwd_desc)

        pwd_form = QFormLayout()
        pwd_form.setSpacing(14)

        self.reset_pwd_username_input = QLineEdit()
        self.reset_pwd_username_input.setPlaceholderText("Enter username to update")
        self.reset_pwd_username_input.setFixedWidth(240)
        self.reset_pwd_username_input.setStyleSheet("padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px;")
        pwd_form.addRow("Username:", self.reset_pwd_username_input)

        self.reset_pwd_new_password_input = QLineEdit()
        self.reset_pwd_new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.reset_pwd_new_password_input.setPlaceholderText("Enter new password")
        self.reset_pwd_new_password_input.setFixedWidth(240)
        self.reset_pwd_new_password_input.setStyleSheet("padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px;")
        pwd_form.addRow("New Password:", self.reset_pwd_new_password_input)

        self.reset_pwd_confirm_password_input = QLineEdit()
        self.reset_pwd_confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.reset_pwd_confirm_password_input.setPlaceholderText("Confirm new password")
        self.reset_pwd_confirm_password_input.setFixedWidth(240)
        self.reset_pwd_confirm_password_input.setStyleSheet("padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px;")
        pwd_form.addRow("Confirm Password:", self.reset_pwd_confirm_password_input)

        pwd_layout.addLayout(pwd_form)

        self.btn_reset_user_password = QPushButton("Change Password")
        self.btn_reset_password = self.btn_reset_user_password  # Alias
        self.btn_reset_user_password.setFixedWidth(240)
        self.btn_reset_user_password.setStyleSheet(
            "QPushButton { background-color: #111111; color: white; padding: 8px; font-weight: bold; border-radius: 4px; } "
            "QPushButton:hover { background-color: #333333; }"
        )
        self.btn_reset_user_password.clicked.connect(self.submit_reset_password)
        self.reset_pwd_confirm_password_input.returnPressed.connect(self.submit_reset_password)
        pwd_layout.addWidget(self.btn_reset_user_password)

        self.reset_pwd_status_label = QLabel("")
        self.reset_pwd_status_label.setStyleSheet("font-size: 13px; font-weight: 500; margin-top: 4px;")
        pwd_layout.addWidget(self.reset_pwd_status_label)
        pwd_layout.addStretch()

        self.user_mgmt_stack.addWidget(self.reset_pwd_widget)

        # Connect action switcher
        self.user_mgmt_action_combo.currentIndexChanged.connect(self.on_user_mgmt_action_changed)

    def on_user_mgmt_action_changed(self, index):
        self.user_mgmt_stack.setCurrentIndex(index)

    def build_add_user_tab(self):
        """Backward compatibility helper."""
        self.build_user_management_tab()
        self.user_mgmt_action_combo.setCurrentIndex(0)

    def build_delete_user_tab(self):
        """Backward compatibility helper."""
        self.build_user_management_tab()
        self.user_mgmt_action_combo.setCurrentIndex(1)

    def submit_add_user(self):
        username = self.new_user_username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Invalid Input", "Username cannot be empty.")
            return

        role_name = self.new_user_role_combo.currentText()
        role_id = self.new_user_role_combo.currentData()
        if role_id is None:
            role_id = self.role_id_map.get(role_name, 2)

        if getattr(self, 'force_mock', False):
            QMessageBox.information(self, "Success", f"User '{username}' with role '{role_name}' created successfully.")
            self.new_user_username_input.clear()
            self.add_user_status_label.setText(f"User '{username}' ({role_name}) created successfully.")
            self.add_user_status_label.setStyleSheet("color: #00aa00; font-size: 13px;")
            return

        try:
            import requests
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            payload = {"username": username, "role_id": int(role_id)}
            resp = self.session.post(f"{self.server_url}/auth/users", json=payload, headers=headers, timeout=5)

            if resp.status_code == 201:
                QMessageBox.information(self, "Success", f"User '{username}' with role '{role_name}' created successfully.")
                self.new_user_username_input.clear()
                self.add_user_status_label.setText(f"User '{username}' ({role_name}) created successfully.")
                self.add_user_status_label.setStyleSheet("color: #00aa00; font-size: 13px;")
            elif resp.status_code == 400:
                detail = resp.json().get("detail", "Username already exists or invalid role")
                QMessageBox.warning(self, "Failed", detail)
                self.add_user_status_label.setText(f"Failed: {detail}")
                self.add_user_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")
            elif resp.status_code == 403:
                detail = resp.json().get("detail", "Admin privileges required")
                QMessageBox.warning(self, "Permission Denied", detail)
                self.add_user_status_label.setText(f"Permission Denied: {detail}")
                self.add_user_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")
            else:
                resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            QMessageBox.warning(self, "Connection Error", f"Could not connect to MaaS backend:\n{e}")
            self.add_user_status_label.setText("Connection error with backend.")
            self.add_user_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error creating user:\n{e}")
            self.add_user_status_label.setText(f"Error: {e}")
            self.add_user_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")

    def add_user(self):
        """Alias for submit_add_user."""
        self.submit_add_user()

    def submit_delete_user(self):
        username = self.delete_user_username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Invalid Input", "Username cannot be empty.")
            return

        if hasattr(self, 'login_username') and self.login_username and username.lower() == self.login_username.lower():
            QMessageBox.warning(self, "Action Prohibited", "You cannot delete your own admin account.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete user '{username}'?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if getattr(self, 'force_mock', False):
            QMessageBox.information(self, "Success", f"User '{username}' deleted successfully.")
            self.delete_user_username_input.clear()
            self.delete_user_status_label.setText(f"User '{username}' deleted successfully.")
            self.delete_user_status_label.setStyleSheet("color: #00aa00; font-size: 13px;")
            return

        try:
            import requests
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            resp = self.session.delete(f"{self.server_url}/auth/users/{username}", headers=headers, timeout=5)

            if resp.status_code == 200:
                QMessageBox.information(self, "Success", f"User '{username}' deleted successfully.")
                self.delete_user_username_input.clear()
                self.delete_user_status_label.setText(f"User '{username}' deleted successfully.")
                self.delete_user_status_label.setStyleSheet("color: #00aa00; font-size: 13px;")
            elif resp.status_code == 404:
                try:
                    detail = resp.json().get("detail", f"User '{username}' not found")
                except Exception:
                    detail = f"User '{username}' not found"
                QMessageBox.warning(self, "Not Found", detail)
                self.delete_user_status_label.setText(f"Failed: {detail}")
                self.delete_user_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")
            elif resp.status_code == 400:
                try:
                    detail = resp.json().get("detail", "Cannot delete user")
                except Exception:
                    detail = "Cannot delete user"
                QMessageBox.warning(self, "Failed", detail)
                self.delete_user_status_label.setText(f"Failed: {detail}")
                self.delete_user_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")
            elif resp.status_code == 403:
                try:
                    detail = resp.json().get("detail", "Admin privileges required")
                except Exception:
                    detail = "Admin privileges required"
                QMessageBox.warning(self, "Permission Denied", detail)
                self.delete_user_status_label.setText(f"Permission Denied: {detail}")
                self.delete_user_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")
            else:
                resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            QMessageBox.warning(self, "Connection Error", f"Could not connect to MaaS backend:\n{e}")
            self.delete_user_status_label.setText("Connection error with backend.")
            self.delete_user_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error deleting user:\n{e}")
            self.delete_user_status_label.setText(f"Error: {e}")
            self.delete_user_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")

    def delete_user(self):
        """Alias for submit_delete_user."""
        self.submit_delete_user()

    def submit_reset_password(self):
        username = self.reset_pwd_username_input.text().strip()
        new_pwd = self.reset_pwd_new_password_input.text()
        conf_pwd = self.reset_pwd_confirm_password_input.text()

        if not username:
            QMessageBox.warning(self, "Invalid Input", "Username cannot be empty.")
            return

        if not new_pwd or not conf_pwd:
            QMessageBox.warning(self, "Invalid Input", "Password fields cannot be empty.")
            return

        if new_pwd != conf_pwd:
            QMessageBox.warning(self, "Invalid Input", "New passwords do not match.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Password Change",
            f"Are you sure you want to change the password for user '{username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if getattr(self, 'force_mock', False):
            QMessageBox.information(self, "Success", f"Password for user '{username}' changed successfully.")
            self.reset_pwd_username_input.clear()
            self.reset_pwd_new_password_input.clear()
            self.reset_pwd_confirm_password_input.clear()
            self.reset_pwd_status_label.setText(f"Password for user '{username}' changed successfully.")
            self.reset_pwd_status_label.setStyleSheet("color: #00aa00; font-size: 13px;")
            return

        try:
            import requests
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            payload = {"new_password": new_pwd}
            resp = self.session.put(f"{self.server_url}/auth/users/{username}/password", json=payload, headers=headers, timeout=5)

            if resp.status_code == 200:
                QMessageBox.information(self, "Success", f"Password for user '{username}' changed successfully.")
                self.reset_pwd_username_input.clear()
                self.reset_pwd_new_password_input.clear()
                self.reset_pwd_confirm_password_input.clear()
                self.reset_pwd_status_label.setText(f"Password for user '{username}' changed successfully.")
                self.reset_pwd_status_label.setStyleSheet("color: #00aa00; font-size: 13px;")
            elif resp.status_code == 404:
                try:
                    detail = resp.json().get("detail", f"User '{username}' not found")
                except Exception:
                    detail = f"User '{username}' not found"
                QMessageBox.warning(self, "Not Found", detail)
                self.reset_pwd_status_label.setText(f"Failed: {detail}")
                self.reset_pwd_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")
            elif resp.status_code == 403:
                try:
                    detail = resp.json().get("detail", "Admin privileges required")
                except Exception:
                    detail = "Admin privileges required"
                QMessageBox.warning(self, "Permission Denied", detail)
                self.reset_pwd_status_label.setText(f"Permission Denied: {detail}")
                self.reset_pwd_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")
            else:
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text
                QMessageBox.warning(self, "Failed", f"Failed to change password: {detail}")
                self.reset_pwd_status_label.setText(f"Failed: {detail}")
                self.reset_pwd_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")
        except requests.exceptions.RequestException as e:
            QMessageBox.warning(self, "Connection Error", f"Could not connect to MaaS backend:\n{e}")
            self.reset_pwd_status_label.setText("Connection error with backend.")
            self.reset_pwd_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error changing password:\n{e}")
            self.reset_pwd_status_label.setText(f"Error: {e}")
            self.reset_pwd_status_label.setStyleSheet("color: #cc0000; font-size: 13px;")

    def reset_user_password(self):
        """Alias for submit_reset_password."""
        self.submit_reset_password()

    def change_user_password(self):
        """Alias for submit_reset_password."""
        self.submit_reset_password()

    def authenticate(self):
        username = self.login_username_input.text().strip()
        password = self.login_password_input.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "Invalid Input", "User Name and Password cannot be empty.")
            return

        if hasattr(self, 'login_server_ip_input'):
            ip_val = self.login_server_ip_input.text().strip()
            if ip_val:
                self.set_server_ip(ip_val)
            
        if getattr(self, 'force_mock', False):
            role = "admin" if username.lower() == "admin" else "operator"
            payload_str = json.dumps({"sub": 1, "role": role})
            b64_payload = base64.urlsafe_b64encode(payload_str.encode()).decode().rstrip("=")
            self.auth_token = f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.{b64_payload}.mock_sig"
            self.login_username = username
        else:
            try:
                import requests
                resp = requests.post(f"{self.server_url}/auth/login", json={"username": username, "password": password}, timeout=5)
                if resp.status_code == 401:
                    QMessageBox.warning(self, "Authentication Failed", "Invalid credentials")
                    return
                resp.raise_for_status()
                self.auth_token = resp.json().get("token")
                self.login_username = username
            except Exception as e:
                QMessageBox.warning(self, "Connection Error", f"Could not connect to backend to authenticate:\n{e}")
                return
            
        self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})

        # Decode JWT token to check user role and determine if admin
        self.jwt_payload = self.decode_jwt_token(self.auth_token)
        self.user_role = str(self.jwt_payload.get("role", "")).lower()
        if getattr(self, 'force_mock', False) and username.lower() == "admin":
            self.user_role = "admin"

        self.update_admin_tab_visibility()
        
        # Set the fixed username
        self.user_name_input.setText(self.login_username)
        self.user_name_input.setReadOnly(True)
        self.user_name_input.setStyleSheet("padding: 4px; border: 1px solid #ccc; border-radius: 4px; background-color: #f0f0f0; color: #555;")
        
        # Switch to main app
        self.stacked_widget.setCurrentWidget(self.main_app_widget)
        self.resize(1000, 700)

    def build_main_app(self):
        self.main_app_widget = QWidget()
        main_layout = QVBoxLayout(self.main_app_widget)
        
        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Build Tabs
        self.build_channels_setup_tab()
        self.build_counter_tab()
        self.build_histogram_tab()
        self.build_coincidences_tab()
        self.build_account_tab()
        
        # Add to TabWidget
        self.tabs.addTab(self.setup_tab, "Channels Setup")
        self.tabs.addTab(self.counter_tab, "Counter")
        self.tabs.addTab(self.histogram_tab, "Histograms")
        self.tabs.addTab(self.coincidences_tab, "Coincidences")
        self.tabs.addTab(self.account_tab, "Account")
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Add + button to tabs
        from PyQt6.QtWidgets import QToolButton
        self.add_tab_btn = QToolButton()
        self.add_tab_btn.setText("+")
        self.add_tab_btn.setFixedSize(25, 25)
        self.add_tab_btn.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.add_tab_btn.clicked.connect(self.add_new_histogram_tab)
        self.tabs.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)

        




    def set_other_tabs_enabled(self, enabled, current_index):
        for i in range(self.tabs.count()):
            if i != current_index:
                self.tabs.setTabEnabled(i, enabled)

    def on_tab_changed(self, index):
        if self.tabs.tabText(index) == "Histograms":
            self.update_histogram_channel_dropdowns()
        elif self.tabs.tabText(index) == "Histograms 2":
            self.update_histogram_channel_dropdowns_2()
        elif self.tabs.tabText(index) == "Coincidences":
            self.update_coincidences_channel_dropdowns()

    def build_account_tab(self):
        self.account_tab = QWidget()
        layout = QVBoxLayout(self.account_tab)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(16)
        layout.setContentsMargins(30, 20, 30, 20)

        # 1. Server Connection Section
        server_section_label = QLabel("MaaS Server Connection")
        server_section_label.setStyleSheet("font-size: 15px; font-weight: bold; margin-bottom: 2px;")
        layout.addWidget(server_section_label)

        server_desc = QLabel("Configure the IP address or hostname of the PC running the MaaS backend for non-local communication.")
        server_desc.setStyleSheet("color: #666; font-size: 12px; margin-bottom: 6px;")
        layout.addWidget(server_desc)

        server_form = QFormLayout()
        self.account_server_ip_input = QLineEdit(getattr(self, 'server_ip', '127.0.0.1'))
        self.account_server_ip_input.setPlaceholderText("e.g. 192.168.1.100 or 192.168.1.100:8000")
        self.account_server_ip_input.setFixedWidth(220)
        self.account_server_ip_input.setStyleSheet("padding: 4px; border: 1px solid #ccc; border-radius: 4px;")
        server_form.addRow("MaaS Server IP:", self.account_server_ip_input)
        layout.addLayout(server_form)

        server_btn_layout = QHBoxLayout()
        self.btn_update_server_ip = QPushButton("Apply Server IP")
        self.btn_update_server_ip.setFixedWidth(130)
        self.btn_update_server_ip.clicked.connect(self.update_server_ip)
        server_btn_layout.addWidget(self.btn_update_server_ip)

        self.btn_test_connection = QPushButton("Test Connection")
        self.btn_test_connection.setFixedWidth(130)
        self.btn_test_connection.clicked.connect(self.test_connection)
        server_btn_layout.addWidget(self.btn_test_connection)
        server_btn_layout.addStretch()
        layout.addLayout(server_btn_layout)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("color: #e0e0e0; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(sep)

        # 2. Change Password Section
        pwd_section_label = QLabel("Account Password Update")
        pwd_section_label.setStyleSheet("font-size: 15px; font-weight: bold; margin-bottom: 2px;")
        layout.addWidget(pwd_section_label)
        
        form_layout = QFormLayout()
        
        self.old_password_input = QLineEdit()
        self.old_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.old_password_input.setFixedWidth(200)
        
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_input.setFixedWidth(200)
        
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input.setFixedWidth(200)
        
        form_layout.addRow("Current Password:", self.old_password_input)
        form_layout.addRow("New Password:", self.new_password_input)
        form_layout.addRow("Confirm New Password:", self.confirm_password_input)
        
        layout.addLayout(form_layout)
        
        self.btn_change_password = QPushButton("Change Password")
        self.btn_change_password.setFixedWidth(200)
        self.btn_change_password.clicked.connect(self.change_password)
        
        layout.addWidget(self.btn_change_password)

    def update_server_ip(self):
        ip = self.account_server_ip_input.text().strip()
        if not ip:
            QMessageBox.warning(self, "Invalid IP", "Please enter a valid IP address or hostname.")
            return
        self.set_server_ip(ip)
        QMessageBox.information(self, "Server IP Updated", f"MaaS server address set to: {self.server_url}")

    def test_connection(self):
        ip = self.account_server_ip_input.text().strip()
        if not ip:
            QMessageBox.warning(self, "Invalid IP", "Please enter a valid IP address or hostname.")
            return
        self.set_server_ip(ip)
        try:
            resp = self.session.get(f"{self.server_url}/health", timeout=3)
            if resp.status_code == 200:
                status_text = "healthy"
                try:
                    data = resp.json()
                    status_text = data.get("status", "healthy")
                except Exception:
                    pass
                QMessageBox.information(
                    self,
                    "Connection Successful",
                    f"Successfully connected to MaaS server at {self.server_url}.\nStatus: {status_text}"
                )
            else:
                QMessageBox.warning(self, "Connection Warning", f"Server responded with HTTP status {resp.status_code} at {self.server_url}.")
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", f"Could not connect to MaaS server at {self.server_url}:\n{e}")

    def change_password(self):
        old_pwd = self.old_password_input.text()
        new_pwd = self.new_password_input.text()
        conf_pwd = self.confirm_password_input.text()
        
        if not old_pwd or not new_pwd or not conf_pwd:
            QMessageBox.warning(self, "Error", "All fields are required.")
            return
            
        if new_pwd != conf_pwd:
            QMessageBox.warning(self, "Error", "New passwords do not match.")
            return

        if getattr(self, 'force_mock', False):
            QMessageBox.information(self, "Success", "Password updated successfully.")
            self.old_password_input.clear()
            self.new_password_input.clear()
            self.confirm_password_input.clear()
            return
            
        try:
            resp = self.session.put(f"{self.server_url}/auth/password", 
                json={"old_password": old_pwd, "new_password": new_pwd}, timeout=5)
            
            if resp.status_code == 200:
                QMessageBox.information(self, "Success", "Password updated successfully.")
                self.old_password_input.clear()
                self.new_password_input.clear()
                self.confirm_password_input.clear()
            else:
                try:
                    err_msg = resp.json().get("detail", resp.text)
                except Exception:
                    err_msg = resp.text
                QMessageBox.warning(self, "Error", f"Failed to update password: {err_msg}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection error: {e}")

    def build_channels_setup_tab(self):
        self.setup_tab = QWidget()
        layout = QVBoxLayout(self.setup_tab)
        
        # User Name input
        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("User Name:"))
        self.user_name_input = QLineEdit("maas-gui-client")
        self.user_name_input.setFixedWidth(150)
        self.user_name_input.setStyleSheet("padding: 4px; border: 1px solid #ccc; border-radius: 4px;")
        user_layout.addWidget(self.user_name_input)
        
        user_layout.addSpacing(20)
        self.btn_book = QPushButton("Book")
        self.btn_book.clicked.connect(self.book_channels)
        user_layout.addWidget(self.btn_book)
        
        user_layout.addSpacing(10)
        self.btn_release = QPushButton("Release")
        self.btn_release.clicked.connect(self.release_channels)
        user_layout.addWidget(self.btn_release)
        
        user_layout.addStretch()
        layout.addLayout(user_layout)
        
        # Grid of channels
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        
        self.channel_nodes = {}
        
        # Top column headers 1-18
        for col in range(1, 19):
            col_label = QLabel(str(col))
            col_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            col_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col_label.setStyleSheet("font-family: 'Segoe UI', Arial; font-weight: 600; font-size: 11px; color: #999;")
            grid_layout.addWidget(col_label, 0, col, Qt.AlignmentFlag.AlignCenter)
            
        # Channels: 1-18
        for row in range(1):
            # Add row label
            row_label = QLabel("Chs")
            row_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            row_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_label.setStyleSheet("font-family: 'Segoe UI', Arial; font-weight: 600; font-size: 12px; color: #777; padding-right: 8px;")
            grid_layout.addWidget(row_label, row + 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            for col in range(1, 19):
                ch = col
                container = ChannelNodeContainer(ch)
                grid_layout.addWidget(container, row + 1, col)
                self.channel_nodes[ch] = container

        # Spacing and stretching to take up full space correctly
        grid_layout.setHorizontalSpacing(15)
        grid_layout.setVerticalSpacing(10)
        grid_layout.setRowStretch(0, 0)
        for row in range(1, 2):
            grid_layout.setRowStretch(row, 1)
        grid_layout.setColumnStretch(0, 0)
        for col in range(1, 19):
            grid_layout.setColumnStretch(col, 1)

        grid_scroll = QScrollArea()
        grid_scroll.setWidget(grid_widget)
        grid_scroll.setWidgetResizable(True)
        
        layout.addWidget(grid_scroll)
        
        self.fetch_booked_channels()

    def fetch_booked_channels(self):
        if getattr(self, 'force_mock', False):
            return
        try:
            resp = self.session.get(f"{self.api_url}/channels", timeout=2)
            if resp.status_code == 200:
                # Clear all first
                for container in self.channel_nodes.values():
                    container.set_booked_by(None, False)
                
                channels_info = resp.json().get("channels", [])
                logger.info(f"Fetched channel status from backend. Found {len(channels_info)} channels.")
                current_user = self.user_name_input.text().strip()
                for ch_info in channels_info:
                    ch_num = ch_info.get("channel_number")
                    status = ch_info.get("status")
                    user_name = ch_info.get("user_name")
                    if status == "booked" and ch_num in self.channel_nodes:
                        is_current = (user_name == current_user)
                        self.channel_nodes[ch_num].set_booked_by(user_name, is_current)
        except Exception as e:
            logger.error(f"Failed to fetch booked channels: {e}")

    def book_channels(self):
        if getattr(self, 'force_mock', False):
            channels = self.get_selected_channels()
            user_name = self.user_name_input.text().strip()
            for ch in channels:
                if ch in self.channel_nodes:
                    self.channel_nodes[ch].set_booked_by(user_name, True)
            return
            
        user_name = self.user_name_input.text().strip()
        if not user_name:
            QMessageBox.warning(self, "Invalid Input", "User Name cannot be empty.")
            return
            
        channels = self.get_selected_channels()
        if not channels:
            QMessageBox.warning(self, "No Channels", "Please select at least one channel to book.")
            return
            
        try:
            payload = {
                "user_name": user_name,
                "channel_numbers": channels
            }
            resp = self.session.post(f"{self.api_url}/channels/book", json=payload, timeout=2)
            if resp.status_code == 201:
                logger.info(f"Booked channels: {channels}")
            else:
                QMessageBox.warning(self, "Booking Failed", f"Could not book channels: {resp.text}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect to backend: {e}")
            
        self.fetch_booked_channels()

    def release_channels(self):
        if getattr(self, 'force_mock', False):
            channels = self.get_selected_channels()
            for ch in channels:
                if ch in self.channel_nodes:
                    self.channel_nodes[ch].set_booked_by(None, False)
            return
            
        user_name = self.user_name_input.text().strip()
        if not user_name:
            return
            
        user_channels = []
        selected_channels = []
        for ch, container in self.channel_nodes.items():
            if container.node.is_current_user:
                user_channels.append(ch)
                if container.node.is_active:
                    selected_channels.append(ch)
                    
        if not selected_channels:
            QMessageBox.warning(self, "No Channels", "Please select at least one of your booked channels to release.")
            return
            
        to_keep = [ch for ch in user_channels if ch not in selected_channels]
        
        try:
            # Release all for user
            resp = self.session.post(f"{self.api_url}/channels/release/{user_name}", timeout=2)
            if resp.status_code == 200:
                logger.info(f"Released all channels for {user_name}")
                # Re-book the ones they want to keep
                if to_keep:
                    payload = {
                        "user_name": user_name,
                        "channel_numbers": to_keep
                    }
                    book_resp = self.session.post(f"{self.api_url}/channels/book", json=payload, timeout=2)
                    if book_resp.status_code != 201:
                        QMessageBox.warning(self, "Re-booking Failed", f"Released channels, but failed to re-book kept channels: {book_resp.text}")
            else:
                QMessageBox.warning(self, "Release Failed", f"Could not release channels: {resp.text}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect to backend: {e}")
            
        self.fetch_booked_channels()

    def build_counter_tab(self):
        self.counter_tab = QWidget()
        layout = QVBoxLayout(self.counter_tab)
        
        # Controls
        controls = QHBoxLayout()
        
        self.btn_play_pause = QPushButton()
        self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play_pause.setToolTip("Start")
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.btn_play_pause = QPushButton()
        self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play_pause.setToolTip("Start")
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)

        self.btn_reset = QPushButton()
        self.btn_reset.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_reset.setToolTip("Reset Data")
        self.btn_reset.setEnabled(False)
        self.btn_reset.clicked.connect(self.reset_measurement)

        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.btn_stop.setToolTip("Stop Measurement (keep data)")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_measurement)
        
        self.btn_zoom = QPushButton("⌕")
        self.btn_zoom.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.btn_zoom.setCheckable(True)
        self.btn_zoom.setToolTip("Toggle Zoom Mode")
        self.btn_zoom.clicked.connect(self.toggle_zoom)

        self.btn_auto_range = QPushButton("⤢")
        self.btn_auto_range.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.btn_auto_range.setToolTip("Enable continuous Auto Range")
        self.btn_auto_range.clicked.connect(self.force_auto_range)
        
        self.btn_export = QPushButton()
        self.btn_export.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.btn_export.setToolTip("Export Data")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_data)
        
        self.binwidth_input = QLineEdit("1e9") # 1e9
        self.binwidth_input.setMaximumWidth(100)
        self.n_values_input = QLineEdit("1000")
        self.n_values_input.setMaximumWidth(80)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Free Running", "Single", "Repeating"])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        
        controls.addWidget(self.btn_play_pause)
        controls.addWidget(self.btn_stop)
        controls.addWidget(self.btn_reset)
        controls.addWidget(self.btn_zoom)
        controls.addWidget(self.btn_auto_range)
        controls.addWidget(self.btn_export)
        
        controls.addSpacing(20)
        controls.addWidget(QLabel("Mode:"))
        controls.addWidget(self.mode_combo)
        
        controls.addSpacing(10)
        controls.addWidget(QLabel("Bin_width (ps):"))
        controls.addWidget(self.binwidth_input)
        self.binwidth_input.returnPressed.connect(self.quick_restart)
        controls.addWidget(QLabel("Bins:"))
        controls.addWidget(self.n_values_input)
        self.n_values_input.returnPressed.connect(self.quick_restart)
        controls.addStretch()
        layout.addLayout(controls)
        
        # Plotting Area using PyQtGraph
        # We use a QGridLayout to overlay the legend on top of the plot
        plot_container_layout = QGridLayout()
        plot_container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.plot_widget = pg.PlotWidget(title="Counts")
        self.plot_widget.setLabel('left', 'Counts / bin')
        self.plot_widget.setLabel('bottom', 'Bin Index')
        self.plot_widget.showGrid(x=True, y=True)
        
        # Default mouse mode to Drag (PanMode)
        self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.PanMode)
        
        # Hover Tooltip & Vertical Line
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('g', width=2))
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        
        self.tooltip_label = pg.TextItem(anchor=(0, 1), color='w', fill=(0, 0, 0, 200))
        self.plot_widget.addItem(self.tooltip_label, ignoreBounds=True)
        self.plot_widget.scene().sigMouseMoved.connect(self.mouse_moved)
        
        plot_container_layout.addWidget(self.plot_widget, 0, 0)
        
        # Overlay Legend with Checkboxes
        self.legend_layout = QVBoxLayout()
        self.legend_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.legend_layout.setContentsMargins(10, 10, 10, 10)
        
        legend_widget = QWidget()
        legend_widget.setObjectName("LegendWidget")
        legend_widget.setLayout(self.legend_layout)
        
        self.legend_scroll = QScrollArea()
        self.legend_scroll.setWidget(legend_widget)
        self.legend_scroll.setWidgetResizable(True)
        self.legend_scroll.setFixedSize(160, 250)
        self.legend_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QWidget#LegendWidget { background-color: rgba(255, 255, 255, 220); border: 1px solid #ccc; border-radius: 6px; }")
        self.legend_scroll.hide() # Hide it initially when there's no data
        
        plot_container_layout.addWidget(self.legend_scroll, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(plot_container_layout)
        
        # Data storage for plotting
        self.history_length = 200
        self.plot_curves = []
        self.data_buffers = []
        self.active_channels_list = []

    def build_coincidences_tab(self):
        self.coincidences_tab = QWidget()
        layout = QVBoxLayout(self.coincidences_tab)
        
        controls = QHBoxLayout()
        
        self.coinc_btn_play_pause = QPushButton()
        self.coinc_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.coinc_btn_play_pause.setToolTip("Start")
        self.coinc_btn_play_pause.clicked.connect(self.toggle_coincidences_play_pause)
        
        self.coinc_btn_reset = QPushButton()
        self.coinc_btn_reset.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.coinc_btn_reset.setToolTip("Reset Data")
        self.coinc_btn_reset.setEnabled(False)
        self.coinc_btn_reset.clicked.connect(self.reset_coincidences_measurement)

        self.coinc_btn_stop = QPushButton()
        self.coinc_btn_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.coinc_btn_stop.setToolTip("Stop Measurement (keep data)")
        self.coinc_btn_stop.setEnabled(False)
        self.coinc_btn_stop.clicked.connect(self.stop_coincidences_measurement)
        
        controls.addWidget(self.coinc_btn_play_pause)
        controls.addWidget(self.coinc_btn_stop)
        controls.addWidget(self.coinc_btn_reset)
        
        controls.addSpacing(20)
        controls.addWidget(QLabel("Coincidence Window (ps):"))
        self.coinc_binwidth_input = QLineEdit("1000")
        self.coinc_binwidth_input.setMaximumWidth(80)
        self.coinc_binwidth_input.setToolTip("Coincidence window in picoseconds (default: 1000 ps = 1 ns)")
        controls.addWidget(self.coinc_binwidth_input)
        
        controls.addSpacing(20)
        controls.addWidget(QLabel("Channels:"))
        self.coinc_channels_layout = QHBoxLayout()
        self.coinc_boxes = []
        self.coinc_combos = self.coinc_boxes
        
        # Initial 1 box by default
        self.add_coincidence_box()
        
        self.coinc_btn_add = QPushButton("+")
        self.coinc_btn_add.setMaximumWidth(30)
        self.coinc_btn_add.setToolTip("Add coincidence channel group")
        self.coinc_btn_add.clicked.connect(self.add_coincidence_box)
        
        self.coinc_btn_remove = QPushButton("-")
        self.coinc_btn_remove.setMaximumWidth(30)
        self.coinc_btn_remove.setToolTip("Remove last coincidence channel group")
        self.coinc_btn_remove.clicked.connect(self.remove_coincidence_box)
        
        controls.addLayout(self.coinc_channels_layout)
        controls.addWidget(self.coinc_btn_add)
        controls.addWidget(self.coinc_btn_remove)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        self.coinc_plot_widget = pg.PlotWidget(axisItems={'bottom': SITimeAxisItem(orientation='bottom')})
        self.coinc_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.coinc_plot_widget.setLabel('bottom', 'Time steps')
        self.coinc_plot_widget.setLabel('left', 'Coincidence Counts')
        self.coinc_legend = self.coinc_plot_widget.addLegend(offset=(10, 10))
        self.coinc_plot_curves = []
        self.coinc_ydata_streams = []
        self.coinc_plot_curve = self.coinc_plot_widget.plot(pen='g')
        layout.addWidget(self.coinc_plot_widget)
        
        self.coinc_worker = None

    def add_coincidence_box(self):
        box = QLineEdit()
        box.setMinimumWidth(80)
        box.setMaximumWidth(140)
        box.setPlaceholderText("e.g. 1, 2, 3")
        box.setToolTip("Enter comma-separated channel numbers (e.g. '1, 2' or '1, 2, 3')")
        self.coinc_boxes.append(box)
        self.coinc_combos = self.coinc_boxes
        self.coinc_channels_layout.addWidget(box)
        self.update_coincidences_channel_dropdowns()

    def remove_coincidence_box(self):
        if len(self.coinc_boxes) > 1:
            box = self.coinc_boxes.pop()
            self.coinc_combos = self.coinc_boxes
            self.coinc_channels_layout.removeWidget(box)
            box.deleteLater()

    def add_coincidence_channel(self):
        self.add_coincidence_box()

    def remove_coincidence_channel(self):
        self.remove_coincidence_box()

    def update_coincidences_channel_dropdowns(self):
        channels = self.get_selected_channels()
        ch_str = ", ".join(str(c) for c in channels) if channels else "None"
        for box in self.coinc_boxes:
            box.setToolTip(f"Enter comma-separated channel numbers (e.g. '1, 2'). Chosen in setup: [{ch_str}]")

    def toggle_coincidences_play_pause(self):
        if self.coinc_worker is None:
            self.start_coincidences_measurement()
        else:
            self.pause_coincidences_measurement()

    def start_coincidences_measurement(self):
        selected_channels = self.get_selected_channels()
        if not selected_channels:
            QMessageBox.warning(
                self,
                "No Channels Selected",
                "No channels were selected in the Channels Setup tab. Please select and activate channels first."
            )
            return

        try:
            window_text = self.coinc_binwidth_input.text().strip()
            window_ps = int(window_text)
            if window_ps <= 0:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Coincidence window must be a positive integer in picoseconds."
            )
            return

        if not self.coinc_boxes:
            QMessageBox.warning(self, "Invalid Selection", "Please add at least one coincidence channel group.")
            return

        coincidences = []
        for idx, box in enumerate(self.coinc_boxes):
            raw_text = box.text().strip()
            box_label = f"group #{idx + 1}" if len(self.coinc_boxes) > 1 else "the coincidence group"
            
            if not raw_text:
                QMessageBox.warning(
                    self,
                    "Invalid Format",
                    f"Please enter comma-separated channels for {box_label} (e.g. '1, 2, 3')."
                )
                box.setFocus()
                return

            tokens = [t.strip() for t in raw_text.split(",")]
            if any(not t for t in tokens):
                QMessageBox.warning(
                    self,
                    "Invalid Format",
                    f"Malformed channel list in {box_label}: '{raw_text}'. Channels must be separated by single commas without empty entries (e.g. '1, 2, 3')."
                )
                box.setFocus()
                return

            group_channels = []
            for t in tokens:
                try:
                    ch = int(t)
                    group_channels.append(ch)
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Invalid Format",
                        f"Invalid channel value '{t}' in {box_label}. All channels must be integer numbers (e.g. '1, 2, 3')."
                    )
                    box.setFocus()
                    return

            if len(group_channels) < 2:
                QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    f"{box_label.capitalize()} must contain at least 2 channels (got {len(group_channels)}: '{raw_text}')."
                )
                box.setFocus()
                return

            if len(set(group_channels)) < len(group_channels):
                QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    f"Duplicate channels detected in {box_label}: '{raw_text}'. Channels within a coincidence group must be distinct."
                )
                box.setFocus()
                return

            unselected = [ch for ch in group_channels if ch not in selected_channels]
            if unselected:
                unselected_str = ", ".join(str(ch) for ch in unselected)
                available_str = ", ".join(str(ch) for ch in selected_channels)
                QMessageBox.warning(
                    self,
                    "Channel Not Selected",
                    f"Channel(s) [{unselected_str}] in {box_label} were not chosen in the initial Channels Setup.\n"
                    f"Available chosen channels: [{available_str}]."
                )
                box.setFocus()
                return

            coincidences.append(group_channels)

        self.coinc_plot_widget.clear()
        if hasattr(self, 'coinc_legend') and self.coinc_legend is not None:
            self.coinc_legend.clear()
        else:
            self.coinc_legend = self.coinc_plot_widget.addLegend(offset=(10, 10))

        palette = ['#00ff00', '#00e5ff', '#ffaa00', '#ff00aa', '#ffff00', '#aa00ff', '#ff5500', '#00aaff']
        self.coinc_plot_curves = []
        self.coinc_ydata_streams = [[] for _ in coincidences]
        self.coinc_groups = coincidences

        for idx, group in enumerate(coincidences):
            color = palette[idx % len(palette)]
            pen = pg.mkPen(color=color, width=2)
            label = f"Coinc {group}"
            curve = self.coinc_plot_widget.plot(pen=pen, name=label)
            self.coinc_plot_curves.append(curve)

        self.coinc_plot_curve = self.coinc_plot_curves[0] if self.coinc_plot_curves else None
        self.coinc_ydata = []

        self.coinc_worker = CoincidencesWorker(
            coincidences=coincidences,
            user_name=self.login_username,
            coincidence_window=window_ps,
            binwidth=int(1e9),
            auth_token=self.auth_token,
            is_mock=self.force_mock,
            server_ip=self.server_ip)
        # Check the booking before starting the worker, so no measurement is
        # ever started on channels the user has not booked.
        if self.coinc_worker.booking_error:
            QMessageBox.critical(self, "Cannot Start Measurement", self.coinc_worker.booking_error)
            self.stop_coincidences_measurement()
            return

        self.coinc_worker.newDataReady.connect(self.update_coincidences_plot)
        self.coinc_worker.start()
        
        from PyQt6.QtWidgets import QStyle
        self.coinc_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.coinc_btn_play_pause.setToolTip("Pause")
        self.coinc_btn_reset.setEnabled(True)
        self.coinc_btn_stop.setEnabled(True)
        self.set_other_tabs_enabled(False, 3)

    def pause_coincidences_measurement(self):
        if self.coinc_worker:
            self.coinc_worker.is_paused = not self.coinc_worker.is_paused
            from PyQt6.QtWidgets import QStyle
            if self.coinc_worker.is_paused:
                self.coinc_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
                self.coinc_btn_play_pause.setToolTip("Resume")
            else:
                self.coinc_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
                self.coinc_btn_play_pause.setToolTip("Pause")


    def stop_coincidences_measurement(self):
        if self.coinc_worker:
            self.coinc_worker.stop()
            self.coinc_worker = None
        from PyQt6.QtWidgets import QStyle
        self.coinc_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.coinc_btn_play_pause.setToolTip("Start")
        self.coinc_btn_reset.setEnabled(True)
        self.coinc_btn_stop.setEnabled(False)
        self.set_other_tabs_enabled(True, 3)

    def reset_coincidences_measurement(self):
        if self.coinc_worker:
            self.coinc_worker.stop()
            self.old_workers.append(self.coinc_worker)
            self.coinc_worker = None
            
        self.coinc_ydata = []
        self.coinc_ydata_streams = []
        self.coinc_plot_curves = []
        self.coinc_plot_widget.clear()
        if hasattr(self, 'coinc_legend') and self.coinc_legend is not None:
            self.coinc_legend.clear()
        self.coinc_plot_curve = self.coinc_plot_widget.plot(pen='g')
        from PyQt6.QtWidgets import QStyle
        self.coinc_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.coinc_btn_play_pause.setToolTip("Start")
        self.coinc_btn_reset.setEnabled(False)
        self.coinc_btn_stop.setEnabled(False)
        self.set_other_tabs_enabled(True, 3)

    def update_coincidences_plot(self, data):
        import numpy as np
        if not hasattr(self, 'coinc_plot_curves') or not self.coinc_plot_curves:
            if not hasattr(self, 'coinc_ydata'):
                self.coinc_ydata = []
            self.coinc_ydata.append(float(np.sum(data)))
            if len(self.coinc_ydata) > 100:
                self.coinc_ydata = self.coinc_ydata[-100:]
            if getattr(self, 'coinc_plot_curve', None):
                self.coinc_plot_curve.setData(self.coinc_ydata)
            return

        if not hasattr(self, 'coinc_ydata_streams') or len(self.coinc_ydata_streams) != len(self.coinc_plot_curves):
            self.coinc_ydata_streams = [[] for _ in self.coinc_plot_curves]

        arr = np.array(data, dtype=float)
        if arr.ndim == 0:
            arr = arr.reshape(1, 1)
        elif arr.ndim == 1:
            if arr.shape[0] == len(self.coinc_plot_curves):
                arr = arr.reshape(-1, 1)
            else:
                arr = arr.reshape(1, -1)

        for i in range(len(self.coinc_plot_curves)):
            if i < arr.shape[0]:
                row = arr[i]
                val = float(np.sum(row))
                self.coinc_ydata_streams[i].append(val)
                if len(self.coinc_ydata_streams[i]) > 100:
                    self.coinc_ydata_streams[i] = self.coinc_ydata_streams[i][-100:]
                self.coinc_plot_curves[i].setData(self.coinc_ydata_streams[i])

        self.coinc_ydata = self.coinc_ydata_streams[0] if self.coinc_ydata_streams else []

    def update_coincidences_stream_plot(self, stream_index, stream_data):
        import numpy as np
        if not hasattr(self, 'coinc_plot_curves') or stream_index >= len(self.coinc_plot_curves):
            return
        if not hasattr(self, 'coinc_ydata_streams') or len(self.coinc_ydata_streams) != len(self.coinc_plot_curves):
            self.coinc_ydata_streams = [[] for _ in self.coinc_plot_curves]

        val = float(np.sum(stream_data))
        self.coinc_ydata_streams[stream_index].append(val)
        if len(self.coinc_ydata_streams[stream_index]) > 100:
            self.coinc_ydata_streams[stream_index] = self.coinc_ydata_streams[stream_index][-100:]
        self.coinc_plot_curves[stream_index].setData(self.coinc_ydata_streams[stream_index])
        if stream_index == 0:
            self.coinc_ydata = self.coinc_ydata_streams[0]


    def add_new_histogram_tab(self):
        if not hasattr(self, 'histogram_tab_2'):
            self.build_histogram_tab_2()
            self.tabs.insertTab(3, self.histogram_tab_2, "Histograms 2")
            self.add_tab_btn.setEnabled(False) # Max 2 tabs

    def build_histogram_tab(self):
        self.histogram_tab = QWidget()
        layout = QVBoxLayout(self.histogram_tab)
        
        # Controls
        controls = QHBoxLayout()
        
        self.hist_btn_play_pause = QPushButton()
        self.hist_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.hist_btn_play_pause.setToolTip("Start")
        self.hist_btn_play_pause.clicked.connect(self.toggle_histogram_play_pause)

        self.hist_btn_reset = QPushButton()
        self.hist_btn_reset.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.hist_btn_reset.setToolTip("Reset Data")
        self.hist_btn_reset.setEnabled(False)
        self.hist_btn_reset.clicked.connect(self.reset_histogram_measurement)

        self.hist_btn_stop = QPushButton()
        self.hist_btn_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.hist_btn_stop.setToolTip("Stop Measurement (keep data)")
        self.hist_btn_stop.setEnabled(False)
        self.hist_btn_stop.clicked.connect(self.stop_histogram_measurement)
        
        self.hist_btn_export = QPushButton()
        self.hist_btn_export.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.hist_btn_export.setToolTip("Export Data")
        self.hist_btn_export.setEnabled(False)
        self.hist_btn_export.clicked.connect(self.export_histogram_data)
        
        self.hist_btn_filter = QPushButton("Filter")
        self.hist_btn_filter.setCheckable(True)
        self.hist_btn_filter.setToolTip("Toggle filter region")
        self.hist_btn_filter.clicked.connect(self.toggle_hist_filter)
        self.hist_btn_filter.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hist_btn_filter.customContextMenuRequested.connect(self.show_filter_context_menu)
        self.hist_btn_filter.hide()
        
        self.hist_btn_add_filter = QPushButton("+")
        self.hist_btn_add_filter.setToolTip("Add second filter")
        self.hist_btn_add_filter.clicked.connect(self.toggle_second_filter)
        self.hist_btn_add_filter.setMaximumWidth(30)
        self.hist_btn_add_filter.hide()
        
        self.hist_mode_combo = QComboBox()
        self.hist_mode_combo.addItems(["Start-Stop", "Histogram", "Correlation"])
        self.hist_mode_combo.currentIndexChanged.connect(self.on_hist_mode_changed)
        
        self.hist_start_combo = QComboBox()
        self.hist_click_combo = QComboBox()
        
        self.hist_binwidth_input = QLineEdit("1000") # 1000 ps
        self.hist_binwidth_input.setMaximumWidth(80)
        self.hist_binwidth_input.returnPressed.connect(self.quick_restart_histogram)
        
        self.hist_n_values_input = QLineEdit("1000")
        self.hist_n_values_input.setMaximumWidth(80)
        self.hist_n_values_input.returnPressed.connect(self.quick_restart_histogram)
        
        self.hist_btn_zoom = QPushButton("⌕")
        self.hist_btn_zoom.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.hist_btn_zoom.setCheckable(True)
        self.hist_btn_zoom.setToolTip("Toggle Zoom Mode")
        self.hist_btn_zoom.clicked.connect(self.hist_toggle_zoom)
        
        self.hist_btn_auto_range = QPushButton("⤢")
        self.hist_btn_auto_range.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.hist_btn_auto_range.setToolTip("Enable Auto Range")
        self.hist_btn_auto_range.clicked.connect(self.hist_force_auto_range)

        controls.addWidget(self.hist_btn_play_pause)
        controls.addWidget(self.hist_btn_stop)
        controls.addWidget(self.hist_btn_reset)
        controls.addWidget(self.hist_btn_zoom)
        controls.addWidget(self.hist_btn_auto_range)
        controls.addWidget(self.hist_btn_export)
        controls.addWidget(self.hist_btn_filter)
        controls.addWidget(self.hist_btn_add_filter)
        
        controls.addSpacing(20)
        controls.addWidget(QLabel("Mode:"))
        controls.addWidget(self.hist_mode_combo)
        
        controls.addSpacing(10)
        controls.addWidget(QLabel("Start Ch:"))
        controls.addWidget(self.hist_start_combo)
        controls.addWidget(QLabel("Click Ch:"))
        controls.addWidget(self.hist_click_combo)
        
        controls.addSpacing(10)
        controls.addWidget(QLabel("Bin_width (ps):"))
        controls.addWidget(self.hist_binwidth_input)
        
        self.lbl_hist_bins = QLabel("Bins:")
        controls.addWidget(self.lbl_hist_bins)
        controls.addWidget(self.hist_n_values_input)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        # Plot
        self.hist_plot_widget = pg.PlotWidget(axisItems={'bottom': SITimeAxisItem(orientation='bottom')})
        self.hist_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.hist_plot_widget.setLabel('bottom', 'Time(s)')
        self.hist_plot_widget.setLabel('left', 'Counts per bin')
        
        self.hist_plot_curve = None
        
        self.hist_region = pg.LinearRegionItem(brush=(255, 255, 0, 50))
        self.hist_region.setZValue(10)
        self.hist_region.hide()
        self.hist_plot_widget.addItem(self.hist_region)

        self.hist_filter_plot_widget = pg.PlotWidget()
        self.hist_filter_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.hist_filter_plot_widget.setLabel('bottom', 'Time (s)')
        self.hist_filter_plot_widget.setLabel('left', 'Sum in Filter')
        self.hist_filter_plot_widget.hide()
        self.hist_filter_curve = self.hist_filter_plot_widget.plot(pen='y')
        
        self.hist_filter_ydata = []
        self.hist_filter_xdata = []
        
        layout.addWidget(self.hist_plot_widget)
        layout.addWidget(self.hist_filter_plot_widget)
        
        layout.setStretchFactor(self.hist_plot_widget, 3)
        layout.setStretchFactor(self.hist_filter_plot_widget, 1)
        
        self.hist_worker = None
        
        # Initialize UI state based on default mode
        self.on_hist_mode_changed()

    def build_histogram_tab_2(self):
        self.histogram_tab_2 = QWidget()
        layout = QVBoxLayout(self.histogram_tab_2)
        
        # Controls
        controls = QHBoxLayout()
        
        self.hist2_btn_play_pause = QPushButton()
        self.hist2_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.hist2_btn_play_pause.setToolTip("Start")
        self.hist2_btn_play_pause.clicked.connect(self.toggle_histogram_play_pause_2)

        self.hist2_btn_reset = QPushButton()
        self.hist2_btn_reset.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.hist2_btn_reset.setToolTip("Reset Data")
        self.hist2_btn_reset.setEnabled(False)
        self.hist2_btn_reset.clicked.connect(self.reset_histogram_measurement_2)

        self.hist2_btn_stop = QPushButton()
        self.hist2_btn_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.hist2_btn_stop.setToolTip("Stop Measurement (keep data)")
        self.hist2_btn_stop.setEnabled(False)
        self.hist2_btn_stop.clicked.connect(self.stop_histogram_measurement_2)
        
        self.hist2_btn_export = QPushButton()
        self.hist2_btn_export.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.hist2_btn_export.setToolTip("Export Data")
        self.hist2_btn_export.setEnabled(False)
        self.hist2_btn_export.clicked.connect(self.export_histogram_data_2)
        
        self.hist2_btn_filter = QPushButton("Filter")
        self.hist2_btn_filter.setCheckable(True)
        self.hist2_btn_filter.setToolTip("Toggle filter region")
        self.hist2_btn_filter.clicked.connect(self.toggle_hist_filter_2)
        self.hist2_btn_filter.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hist2_btn_filter.customContextMenuRequested.connect(self.show_filter_context_menu_2)
        self.hist2_btn_filter.hide()
        
        self.hist2_btn_add_filter = QPushButton("+")
        self.hist2_btn_add_filter.setToolTip("Add second filter")
        self.hist2_btn_add_filter.clicked.connect(self.toggle_second_filter_2)
        self.hist2_btn_add_filter.setMaximumWidth(30)
        self.hist2_btn_add_filter.hide()
        
        self.hist2_mode_combo = QComboBox()
        self.hist2_mode_combo.addItems(["Start-Stop", "Histogram", "Correlation"])
        self.hist2_mode_combo.currentIndexChanged.connect(self.on_hist_mode_changed_2)
        
        self.hist2_start_combo = QComboBox()
        self.hist2_click_combo = QComboBox()
        
        self.hist2_binwidth_input = QLineEdit("1000") # 1000 ps
        self.hist2_binwidth_input.setMaximumWidth(80)
        self.hist2_binwidth_input.returnPressed.connect(self.quick_restart_histogram)
        
        self.hist2_n_values_input = QLineEdit("1000")
        self.hist2_n_values_input.setMaximumWidth(80)
        self.hist2_n_values_input.returnPressed.connect(self.quick_restart_histogram)
        
        self.hist2_btn_zoom = QPushButton("⌕")
        self.hist2_btn_zoom.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.hist2_btn_zoom.setCheckable(True)
        self.hist2_btn_zoom.setToolTip("Toggle Zoom Mode")
        self.hist2_btn_zoom.clicked.connect(self.hist_toggle_zoom_2)
        
        self.hist2_btn_auto_range = QPushButton("⤢")
        self.hist2_btn_auto_range.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.hist2_btn_auto_range.setToolTip("Enable Auto Range")
        self.hist2_btn_auto_range.clicked.connect(self.hist_force_auto_range_2)

        controls.addWidget(self.hist2_btn_play_pause)
        controls.addWidget(self.hist2_btn_stop)
        controls.addWidget(self.hist2_btn_reset)
        controls.addWidget(self.hist2_btn_zoom)
        controls.addWidget(self.hist2_btn_auto_range)
        controls.addWidget(self.hist2_btn_export)
        controls.addWidget(self.hist2_btn_filter)
        controls.addWidget(self.hist2_btn_add_filter)
        
        controls.addSpacing(20)
        controls.addWidget(QLabel("Mode:"))
        controls.addWidget(self.hist2_mode_combo)
        
        controls.addSpacing(10)
        controls.addWidget(QLabel("Start Ch:"))
        controls.addWidget(self.hist2_start_combo)
        controls.addWidget(QLabel("Click Ch:"))
        controls.addWidget(self.hist2_click_combo)
        
        controls.addSpacing(10)
        controls.addWidget(QLabel("Bin_width (ps):"))
        controls.addWidget(self.hist2_binwidth_input)
        
        self.lbl_hist_bins = QLabel("Bins:")
        controls.addWidget(self.lbl_hist_bins)
        controls.addWidget(self.hist2_n_values_input)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        # Plot
        self.hist2_plot_widget = pg.PlotWidget(axisItems={'bottom': SITimeAxisItem(orientation='bottom')})
        self.hist2_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.hist2_plot_widget.setLabel('bottom', 'Time(s)')
        self.hist2_plot_widget.setLabel('left', 'Counts per bin')
        
        self.hist2_plot_curve = None
        
        self.hist2_region = pg.LinearRegionItem(brush=(255, 255, 0, 50))
        self.hist2_region.setZValue(10)
        self.hist2_region.hide()
        self.hist2_plot_widget.addItem(self.hist2_region)

        self.hist2_filter_plot_widget = pg.PlotWidget()
        self.hist2_filter_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.hist2_filter_plot_widget.setLabel('bottom', 'Time (s)')
        self.hist2_filter_plot_widget.setLabel('left', 'Sum in Filter')
        self.hist2_filter_plot_widget.hide()
        self.hist2_filter_curve = self.hist2_filter_plot_widget.plot(pen='y')
        
        self.hist2_filter_ydata = []
        self.hist2_filter_xdata = []
        
        layout.addWidget(self.hist2_plot_widget)
        layout.addWidget(self.hist2_filter_plot_widget)
        
        layout.setStretchFactor(self.hist2_plot_widget, 3)
        layout.setStretchFactor(self.hist2_filter_plot_widget, 1)
        
        self.hist2_worker = None
        
        # Initialize UI state based on default mode
        self.on_hist_mode_changed_2()

    def update_histogram_channel_dropdowns(self):
        channels = self.get_selected_channels()
        channels_str = [str(ch) for ch in channels]
        
        # Save current selections
        curr_start = self.hist_start_combo.currentText()
        curr_click = self.hist_click_combo.currentText()
        
        self.hist_start_combo.clear()
        self.hist_click_combo.clear()
        
        if channels_str:
            self.hist_start_combo.addItems(channels_str)
            self.hist_click_combo.addItems(channels_str)
            
            # Set initial defaults to different channels if possible
            if not curr_start and not curr_click and len(channels_str) >= 2:
                self.hist_start_combo.setCurrentText(channels_str[0])
                self.hist_click_combo.setCurrentText(channels_str[1])
            else:
                # Restore if still valid
                if curr_start in channels_str:
                    self.hist_start_combo.setCurrentText(curr_start)
                if curr_click in channels_str:
                    self.hist_click_combo.setCurrentText(curr_click)


    def update_histogram_channel_dropdowns_2(self):
        channels = self.get_selected_channels()
        channels_str = [str(ch) for ch in channels]
        
        # Save current selections
        curr_start = self.hist2_start_combo.currentText()
        curr_click = self.hist2_click_combo.currentText()
        
        self.hist2_start_combo.clear()
        self.hist2_click_combo.clear()
        
        if channels_str:
            self.hist2_start_combo.addItems(channels_str)
            self.hist2_click_combo.addItems(channels_str)
            
            # Set initial defaults to different channels if possible
            if not curr_start and not curr_click and len(channels_str) >= 2:
                self.hist2_start_combo.setCurrentText(channels_str[0])
                self.hist2_click_combo.setCurrentText(channels_str[1])
            else:
                # Restore if still valid
                if curr_start in channels_str:
                    self.hist2_start_combo.setCurrentText(curr_start)
                if curr_click in channels_str:
                    self.hist2_click_combo.setCurrentText(curr_click)


    def on_mode_changed(self):
        mode = self.mode_combo.currentText()
        if mode == "Repeating":
            self.binwidth_input.setEnabled(True)
            self.binwidth_input.setText("1e12") # Default to 1 second bins for repeating
            self.n_values_input.setText("1")
            self.n_values_input.setEnabled(False)
            self.plot_widget.setLabel('bottom', 'Time Steps')
            self.plot_widget.setLabel('left', 'Total Counts')
            self.plot_widget.setMouseEnabled(x=True, y=True)
        else:
            self.binwidth_input.setEnabled(True)
            self.n_values_input.setEnabled(True)
            self.plot_widget.setLabel('bottom', 'Bin Index')
            self.plot_widget.setLabel('left', 'Counts / bin')
            self.plot_widget.setMouseEnabled(x=True, y=True)

    def toggle_zoom(self, checked):
        if checked:
            self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        else:
            self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.PanMode)

    def force_auto_range(self):
        self.plot_widget.enableAutoRange()

    def mouse_moved(self, evt):
        pos = evt
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            x_val = mouse_point.x()
            self.v_line.setPos(x_val)
            
            x_idx = int(round(x_val))
            if self.active_channels_list and self.data_buffers and 0 <= x_idx < len(self.data_buffers[0]):
                text = f"Bin: {x_idx}<br>"
                for i, ch in enumerate(self.active_channels_list):
                    curve = self.plot_curves[i]
                    if curve.isVisible():
                        y_val = self.data_buffers[i][x_idx]
                        text += f"Ch {ch}: {y_val:.1f}<br>"
                
                self.tooltip_label.setHtml(f"<div style='text-align: left'>{text}</div>")
                self.tooltip_label.setPos(x_val, mouse_point.y())

    def get_selected_channels(self):
        channels = []
        for ch, container in self.channel_nodes.items():
            if container.node.is_active:
                channels.append(ch)
        return sorted(channels)

    def start_measurement(self):
        # Verify Backend Health (skipped in testing mode, which uses generated test data)
        if not self.force_mock:
            try:
                health_resp = self.session.get(f"{self.server_url}/health", timeout=2)
                healthy = health_resp.status_code == 200 and health_resp.json().get("status") == "healthy"
                if not healthy:
                    logger.error(f"MaaS backend is not healthy. Status Code: {health_resp.status_code}.")
                    QMessageBox.critical(self, "Backend Unavailable", f"The MaaS backend is not healthy (status code {health_resp.status_code}). Cannot start measurement.")
                    return
            except Exception as e:
                logger.error(f"Could not connect to the MaaS backend: {e}")
                QMessageBox.critical(self, "Backend Unavailable", f"Could not connect to the MaaS backend at {self.server_url}.\n\n{e}")
                return

        channels = self.get_selected_channels()
        if not channels:
            QMessageBox.warning(self, "No Channels", "Please select at least one channel from the Channels Setup tab.")
            return

        try:
            binwidth = float(self.binwidth_input.text())
            n_values = int(self.n_values_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numbers for Binwidth and n_values.")
            return

        # Initialize plot curves only if we are starting a completely new measurement
        if self.worker is None:
            self.plot_widget.clear()
            
            # Re-add persistent items after clearing
            self.plot_widget.addItem(self.v_line, ignoreBounds=True)
            self.plot_widget.addItem(self.tooltip_label, ignoreBounds=True)
            
            mode = self.mode_combo.currentText()
            if mode in ["Free Running", "Single"]:
                # Remove limits so the magnifier tool works
                self.plot_widget.getViewBox().setLimits(xMin=None, xMax=None, minXRange=None, maxXRange=None)
                self.plot_widget.setXRange(0, n_values, padding=0)
                self.plot_widget.enableAutoRange(axis='y')
            else:
                # Remove limits for Repeating mode
                self.plot_widget.getViewBox().setLimits(xMin=None, xMax=None, minXRange=None, maxXRange=None)
                self.plot_widget.enableAutoRange(axis='y')
            
            # Clear old checkboxes
            for i in reversed(range(self.legend_layout.count())):
                widget = self.legend_layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)
            
            self.plot_curves = []
            
            mode = self.mode_combo.currentText()
            if mode == "Repeating":
                # For repeating, we keep a dynamic list up to 1000 items
                self.history_length = 1000
                self.data_buffers = [[] for _ in channels]
            else:
                self.data_buffers = [np.zeros(n_values) for _ in channels]
                
            self.active_channels_list = channels
            
            # Expanded variety of distinct colors
            colors = [
                (214, 39, 40),   # Red
                (31, 119, 180),  # Blue
                (44, 160, 44),   # Green
                (255, 127, 14),  # Orange
                (148, 103, 189), # Purple
                (140, 86, 75),   # Brown
                (227, 119, 194), # Pink
                (188, 189, 34),  # Olive
                (23, 190, 207),  # Cyan
                (255, 0, 255),   # Magenta
                (50, 205, 50),   # Lime
                (255, 215, 0),   # Gold
                (250, 128, 114), # Salmon
                (0, 128, 128),   # Teal
                (100, 149, 237), # Cornflower Blue
                (199, 21, 133),  # Medium Violet Red
            ]
            
            for i, ch in enumerate(channels):
                rgb = colors[i % len(colors)]
                pen = pg.mkPen(color=rgb, width=2)
                curve = self.plot_widget.plot(pen=pen, name=f"Channel {ch}")
                self.plot_curves.append(curve)
                
                # Add Legend Checkbox
                cb = QCheckBox(f"Channel {ch}")
                cb.setChecked(True)
                cb.setStyleSheet(f"color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]}); font-weight: bold;")
                cb.stateChanged.connect(lambda state, c=curve: c.setVisible(state == Qt.CheckState.Checked.value))
                self.legend_layout.addWidget(cb)
            
            self.legend_scroll.show()

        # Initialize and start the background thread
        if self.worker is None:
            user_name = self.user_name_input.text().strip()
            if not user_name:
                QMessageBox.warning(self, "Invalid Name", "Please enter a user name.")
                return
                
            # Base refresh rate for Free Running / Single is 25Hz
            refresh_rate = 25
                
            mode = self.mode_combo.currentText()
            
            # Dynamic Y-axis label for Repeating mode based on binwidth
            if mode == "Repeating":
                if binwidth == 1e12:
                    self.plot_widget.setLabel('left', 'Counts / 1s')
                elif binwidth == 1e9:
                    self.plot_widget.setLabel('left', 'Counts / 1ms')
                elif binwidth == 1e6:
                    self.plot_widget.setLabel('left', 'Counts / 1us')
                else:
                    self.plot_widget.setLabel('left', f'Counts / {binwidth}ps')
            
            self.worker = CountRateWorker(channels, user_name, binwidth, n_values, refresh_rate, mode=mode, auth_token=self.auth_token, is_mock=self.force_mock, server_ip=self.server_ip)
            self.worker.finished.connect(self.on_worker_finished)
            
            if self.worker.booking_error:
                QMessageBox.critical(self, "Cannot Start Measurement", self.worker.booking_error)
                self.worker = None
                return
                
            self.worker.newDataReady.connect(self.update_plot)
            self.worker.start()
            logger.info(f"Measurement started successfully for user {user_name} on channels {channels} with binwidth={binwidth}, n_values={n_values}, refresh={refresh_rate}Hz")
        self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.btn_play_pause.setToolTip("Pause")
        self.btn_reset.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.btn_export.setEnabled(False)
        
        mode = self.mode_combo.currentText()
        if mode != "Single":
            self.binwidth_input.setEnabled(False)
            if mode != "Repeating":
                self.n_values_input.setEnabled(False)
                
        self.mode_combo.setEnabled(False)
        self.set_other_tabs_enabled(False, 1) # Disable other tabs while running or paused

    def quick_restart(self):
        # Only allow quick restart while running if it's Single mode
        if self.worker is not None and self.mode_combo.currentText() != "Single":
            return
            
        if self.worker:
            self.worker.stop()
            self.old_workers.append(self.worker)
            self.worker = None
            
        self.start_measurement()

    def on_worker_finished(self):
        # Restore UI when Single measurement completes naturally
        if self.worker is None:
            return
            
        logger.info("Worker thread finished naturally. Restoring UI state.")
        self.btn_play_pause.setEnabled(True)
        self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play_pause.setToolTip("Start")
        self.btn_reset.setEnabled(True)
        
        mode = self.mode_combo.currentText()
        if mode != "Repeating":
            self.binwidth_input.setEnabled(True)
            self.n_values_input.setEnabled(True)
        self.mode_combo.setEnabled(True)
        self.set_other_tabs_enabled(True, 1)
        self.worker = None

    def update_plot(self, rates_2d):
        mode = self.mode_combo.currentText()
        for i in range(len(self.plot_curves)):
            if i < rates_2d.shape[0]:
                if mode == "Free Running" or mode == "Single":
                    self.data_buffers[i] += rates_2d[i]
                elif mode == "Repeating":
                    # Append new value, pop oldest if we exceed history
                    val = rates_2d[i][0] if len(rates_2d[i]) > 0 else 0
                    self.data_buffers[i].append(val)
                    if len(self.data_buffers[i]) > self.history_length:
                        self.data_buffers[i].pop(0)
                
                plot_data = self.data_buffers[i]
                
                self.plot_curves[i].setData(plot_data)
                
            if mode == "Repeating":
                # Enforce a 60-point sliding window so points are spaced out nicely
                current_len = max(len(buf) for buf in self.data_buffers)
                window_size = 60
                if current_len > window_size:
                    self.plot_widget.setXRange(current_len - window_size, current_len, padding=0)
                else:
                    self.plot_widget.setXRange(0, window_size, padding=0)
                    
        self.btn_export.setEnabled(True)

    def toggle_play_pause(self):
        if self.worker is None:
            self.start_measurement()
        else:
            self.pause_measurement()

    def pause_measurement(self):
        if self.worker:
            self.worker.is_paused = not self.worker.is_paused
            if self.worker.is_paused:
                self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
                self.btn_play_pause.setToolTip("Resume")
                self.btn_export.setEnabled(True)
            else:
                self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
                self.btn_play_pause.setToolTip("Pause")
                self.btn_export.setEnabled(False)


    def stop_measurement(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        from PyQt6.QtWidgets import QStyle
        self.btn_play_pause.setEnabled(True)
        self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play_pause.setToolTip("Start")
        self.btn_reset.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_export.setEnabled(True)
        
        mode = self.mode_combo.currentText()
        if mode != "Repeating":
            self.binwidth_input.setEnabled(True)
            self.n_values_input.setEnabled(True)
        self.mode_combo.setEnabled(True)
        self.set_other_tabs_enabled(True, 1)

    def reset_measurement(self):
        if self.worker:
            self.worker.stop()
            self.old_workers.append(self.worker)
            self.worker = None
            
        self.plot_widget.clear()
        
        # Clear checkboxes
        for i in reversed(range(self.legend_layout.count())):
            widget = self.legend_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                
        self.legend_scroll.hide()
        self.plot_curves = []
        self.data_buffers = []
        self.active_channels_list = []
        
        # Keep persistent items
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        self.plot_widget.addItem(self.tooltip_label, ignoreBounds=True)
        
        self.btn_play_pause.setEnabled(True)
        self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play_pause.setToolTip("Start")
        self.btn_reset.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_export.setEnabled(False)
        
        mode = self.mode_combo.currentText()
        if mode != "Repeating":
            self.binwidth_input.setEnabled(True)
            self.n_values_input.setEnabled(True)
        self.mode_combo.setEnabled(True)
        
        self.set_other_tabs_enabled(True, 1)

    def start_histogram_measurement(self):
        try:
            start_ch = int(self.hist_start_combo.currentText())
            click_ch = int(self.hist_click_combo.currentText())
            binwidth = float(self.hist_binwidth_input.text())
            n_values = int(self.hist_n_values_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numbers for Binwidth and n_values.")
            return

        if self.hist_worker is None:
            self.hist_plot_widget.clear()
            self.hist_plot_curve = self.hist_plot_widget.plot(pen='b')
            self.hist_plot_widget.addItem(self.hist_region)
            if hasattr(self, 'hist_region_2'):
                self.hist_plot_widget.addItem(self.hist_region_2)
            if not self.hist_btn_filter.isChecked():
                self.hist_region.hide()
                if hasattr(self, 'hist_region_2'):
                    self.hist_region_2.hide()
            self.hist_data_buffer = np.zeros(n_values)
            self.hist_x_buffer = np.zeros(n_values)

        user_name = self.user_name_input.text().strip() or "maas-gui-client"
        mode = self.hist_mode_combo.currentText()

        self.hist_worker = HistogramWorker(
            start_channel=start_ch,
            click_channel=click_ch,
            user_name=user_name,
            binwidth=binwidth,
            n_values=n_values,
            mode=mode,
            auth_token=self.auth_token,
            is_mock=self.force_mock,
            server_ip=self.server_ip
        )

        if self.hist_worker.booking_error:
            QMessageBox.warning(self, "Cannot Start Measurement", self.hist_worker.booking_error)
            self.hist_worker = None
            return

        self.hist_worker.newDataReady.connect(self.update_histogram_plot)
        self.hist_worker.finished.connect(self.on_histogram_worker_finished)
        self.hist_worker.start()

        self.hist_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.hist_btn_play_pause.setToolTip("Pause")
        self.hist_btn_reset.setEnabled(True)
        self.hist_btn_stop.setEnabled(True)
        self.hist_btn_export.setEnabled(False)
        
        self.hist_binwidth_input.setEnabled(False)
        self.hist_n_values_input.setEnabled(False)
        self.hist_mode_combo.setEnabled(False)
        self.hist_start_combo.setEnabled(False)
        self.hist_click_combo.setEnabled(False)

        self.set_other_tabs_enabled(False, 2)
        
    def start_histogram_measurement_2(self):
        try:
            start_ch = int(self.hist2_start_combo.currentText())
            click_ch = int(self.hist2_click_combo.currentText())
            binwidth = float(self.hist2_binwidth_input.text())
            n_values = int(self.hist2_n_values_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numbers for Binwidth and n_values.")
            return

        if self.hist2_worker is None:
            self.hist2_plot_widget.clear()
            self.hist2_plot_curve = self.hist2_plot_widget.plot(pen='b')
            self.hist2_plot_widget.addItem(self.hist2_region)
            if hasattr(self, 'hist_region_2'):
                self.hist2_plot_widget.addItem(self.hist2_region_2)
            if not self.hist2_btn_filter.isChecked():
                self.hist2_region.hide()
                if hasattr(self, 'hist_region_2'):
                    self.hist2_region_2.hide()
            self.hist2_data_buffer = np.zeros(n_values)
            self.hist2_x_buffer = np.zeros(n_values)

        user_name = self.user_name_input.text().strip() or "maas-gui-client"
        mode = self.hist2_mode_combo.currentText()

        self.hist2_worker = HistogramWorker(
            start_channel=start_ch,
            click_channel=click_ch,
            user_name=user_name,
            binwidth=binwidth,
            n_values=n_values,
            mode=mode,
            auth_token=self.auth_token,
            is_mock=self.force_mock,
            server_ip=self.server_ip
        )

        if self.hist2_worker.booking_error:
            QMessageBox.warning(self, "Cannot Start Measurement", self.hist2_worker.booking_error)
            self.hist2_worker = None
            return

        self.hist2_worker.newDataReady.connect(self.update_histogram_plot_2)
        self.hist2_worker.finished.connect(self.on_histogram_worker_finished_2)
        self.hist2_worker.start()

        self.hist2_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.hist2_btn_play_pause.setToolTip("Pause")
        self.hist2_btn_reset.setEnabled(True)
        self.hist2_btn_stop.setEnabled(True)
        self.hist2_btn_export.setEnabled(False)
        
        self.hist2_binwidth_input.setEnabled(False)
        self.hist2_n_values_input.setEnabled(False)
        self.hist2_mode_combo.setEnabled(False)
        self.hist2_start_combo.setEnabled(False)
        self.hist2_click_combo.setEnabled(False)

        self.set_other_tabs_enabled(False, 3)
        
    def format_time_string(self, s_val):
        abs_val = abs(s_val)
        if abs_val == 0:
            return "0s"
        elif abs_val >= 1.0:
            return f"{s_val:.3g}s"
        elif abs_val >= 1e-3:
            return f"{s_val * 1e3:.3g}ms"
        elif abs_val >= 1e-6:
            return f"{s_val * 1e6:.3g}us"
        elif abs_val >= 1e-9:
            return f"{s_val * 1e9:.3g}ns"
        else:
            return f"{s_val * 1e12:.3g}ps"

    def format_time_string_2(self, s_val):
        abs_val = abs(s_val)
        if abs_val == 0:
            return "0s"
        elif abs_val >= 1.0:
            return f"{s_val:.3g}s"
        elif abs_val >= 1e-3:
            return f"{s_val * 1e3:.3g}ms"
        elif abs_val >= 1e-6:
            return f"{s_val * 1e6:.3g}us"
        elif abs_val >= 1e-9:
            return f"{s_val * 1e9:.3g}ns"
        else:
            return f"{s_val * 1e12:.3g}ps"

    def parse_time_string(self, text):
        import re
        text = text.strip().lower()
        match = re.match(r"^(-?[\d\.]+(?:e-?\d+)?)\s*(ps|ns|us|ms|s)?$", text)
        if not match:
            raise ValueError("Invalid format")
        val_str, unit = match.groups()
        val = float(val_str)
        if unit == "ms":
            val *= 1e-3
        elif unit == "us":
            val *= 1e-6
        elif unit == "ns":
            val *= 1e-9
        elif unit == "ps":
            val *= 1e-12
        return val

    def toggle_second_filter(self):
        if not getattr(self, 'second_filter_active', False):
            self.second_filter_active = True
            self.hist_btn_add_filter.setText("-")
            self.hist_btn_add_filter.setToolTip("Remove second filter")
            
            if not hasattr(self, 'hist_region_2'):
                self.hist_region_2 = pg.LinearRegionItem(brush=(0, 255, 255, 50))
                self.hist_region_2.setZValue(10)
                self.hist_plot_widget.addItem(self.hist_region_2)
                self.hist_filter_curve_2 = self.hist_filter_plot_widget.plot(pen='c')
                
            self.hist_region_2.show()
            
            if hasattr(self, 'hist_x_buffer') and len(self.hist_x_buffer) > 0:
                mid = len(self.hist_x_buffer) // 2
                span = (self.hist_x_buffer[-1] - self.hist_x_buffer[0]) * 0.1
                if span == 0: span = 1
                self.hist_region_2.setRegion([self.hist_x_buffer[mid], self.hist_x_buffer[mid] + span*2])
                
            self.hist_filter_ydata_2 = []
            if hasattr(self, 'hist_filter_ydata') and len(self.hist_filter_ydata) > 0:
                self.hist_filter_ydata_2 = [0] * len(self.hist_filter_ydata)
        else:
            self.second_filter_active = False
            self.hist_btn_add_filter.setText("+")
            self.hist_btn_add_filter.setToolTip("Add second filter")
            if hasattr(self, 'hist_region_2'):
                self.hist_region_2.hide()
                self.hist_filter_curve_2.setData([], [])

    def toggle_second_filter_2(self):
        if not getattr(self, 'second_filter_active', False):
            self.second_filter_active = True
            self.hist2_btn_add_filter.setText("-")
            self.hist2_btn_add_filter.setToolTip("Remove second filter")
            
            if not hasattr(self, 'hist_region_2'):
                self.hist2_region_2 = pg.LinearRegionItem(brush=(0, 255, 255, 50))
                self.hist2_region_2.setZValue(10)
                self.hist2_plot_widget.addItem(self.hist2_region_2)
                self.hist2_filter_curve_2 = self.hist2_filter_plot_widget.plot(pen='c')
                
            self.hist2_region_2.show()
            
            if hasattr(self, 'hist_x_buffer') and len(self.hist2_x_buffer) > 0:
                mid = len(self.hist2_x_buffer) // 2
                span = (self.hist2_x_buffer[-1] - self.hist2_x_buffer[0]) * 0.1
                if span == 0: span = 1
                self.hist2_region_2.setRegion([self.hist2_x_buffer[mid], self.hist2_x_buffer[mid] + span*2])
                
            self.hist2_filter_ydata_2 = []
            if hasattr(self, 'hist_filter_ydata') and len(self.hist2_filter_ydata) > 0:
                self.hist2_filter_ydata_2 = [0] * len(self.hist2_filter_ydata)
        else:
            self.second_filter_active = False
            self.hist2_btn_add_filter.setText("+")
            self.hist2_btn_add_filter.setToolTip("Add second filter")
            if hasattr(self, 'hist_region_2'):
                self.hist2_region_2.hide()
                self.hist2_filter_curve_2.setData([], [])

    def show_filter_context_menu(self, pos):
        if not hasattr(self, 'hist_btn_filter') or not self.hist_btn_filter.isChecked():
            return
            
        menu = QMenu(self)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        def create_row(label_text, region_item):
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            
            min_input = QLineEdit()
            min_input.setPlaceholderText("Min")
            min_input.setMaximumWidth(80)
            
            max_input = QLineEdit()
            max_input.setPlaceholderText("Max")
            max_input.setMaximumWidth(80)
            
            minX, maxX = region_item.getRegion()
            min_input.setText(self.format_time_string(minX))
            max_input.setText(self.format_time_string(maxX))
            
            row.addWidget(min_input)
            row.addWidget(QLabel("-"))
            row.addWidget(max_input)
            return row, min_input, max_input
            
        row1, min1, max1 = create_row("F1 (Yellow):", self.hist_region)
        layout.addLayout(row1)
        
        has_f2 = getattr(self, 'second_filter_active', False)
        if has_f2:
            row2, min2, max2 = create_row("F2 (Cyan):", self.hist_region_2)
            layout.addLayout(row2)
            
        def on_enter():
            try:
                self.hist_region.setRegion([self.parse_time_string(min1.text()), self.parse_time_string(max1.text())])
                if has_f2:
                    self.hist_region_2.setRegion([self.parse_time_string(min2.text()), self.parse_time_string(max2.text())])
                menu.close()
            except ValueError:
                pass
                
        min1.returnPressed.connect(on_enter)
        max1.returnPressed.connect(on_enter)
        if has_f2:
            min2.returnPressed.connect(on_enter)
            max2.returnPressed.connect(on_enter)
            
        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)
        menu.addAction(action)
        menu.exec(self.hist_btn_filter.mapToGlobal(pos))

    def show_filter_context_menu_2(self, pos):
        if not hasattr(self, 'hist_btn_filter') or not self.hist2_btn_filter.isChecked():
            return
            
        menu = QMenu(self)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        def create_row(label_text, region_item):
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            
            min_input = QLineEdit()
            min_input.setPlaceholderText("Min")
            min_input.setMaximumWidth(80)
            
            max_input = QLineEdit()
            max_input.setPlaceholderText("Max")
            max_input.setMaximumWidth(80)
            
            minX, maxX = region_item.getRegion()
            min_input.setText(self.format_time_string(minX))
            max_input.setText(self.format_time_string(maxX))
            
            row.addWidget(min_input)
            row.addWidget(QLabel("-"))
            row.addWidget(max_input)
            return row, min_input, max_input
            
        row1, min1, max1 = create_row("F1 (Yellow):", self.hist2_region)
        layout.addLayout(row1)
        
        has_f2 = getattr(self, 'second_filter_active', False)
        if has_f2:
            row2, min2, max2 = create_row("F2 (Cyan):", self.hist2_region_2)
            layout.addLayout(row2)
            
        def on_enter():
            try:
                self.hist2_region.setRegion([self.parse_time_string(min1.text()), self.parse_time_string(max1.text())])
                if has_f2:
                    self.hist2_region_2.setRegion([self.parse_time_string(min2.text()), self.parse_time_string(max2.text())])
                menu.close()
            except ValueError:
                pass
                
        min1.returnPressed.connect(on_enter)
        max1.returnPressed.connect(on_enter)
        if has_f2:
            min2.returnPressed.connect(on_enter)
            max2.returnPressed.connect(on_enter)
            
        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)
        menu.addAction(action)
        menu.exec(self.hist2_btn_filter.mapToGlobal(pos))

    def toggle_hist_filter(self):
        if self.hist_btn_filter.isChecked():
            self.hist_region.show()
            self.hist_filter_plot_widget.show()
            self.hist_btn_add_filter.show()
            if getattr(self, 'second_filter_active', False) and hasattr(self, 'hist_region_2'):
                self.hist_region_2.show()
            self.hist_filter_ydata = []
            if getattr(self, 'second_filter_active', False):
                self.hist_filter_ydata_2 = []
            self.hist_filter_xdata = []
            self.hist_filter_curve.setData([], [])
            if hasattr(self, 'hist_filter_curve_2'):
                self.hist_filter_curve_2.setData([], [])
            
            import time
            self.hist_filter_start_time = time.time()
            
            if hasattr(self, 'hist_x_buffer') and self.hist_x_buffer is not None and len(self.hist_x_buffer) > 0:
                mid = len(self.hist_x_buffer) // 2
                span = (self.hist_x_buffer[-1] - self.hist_x_buffer[0]) * 0.1
                if span == 0: span = 1
                self.hist_region.setRegion([self.hist_x_buffer[mid] - span, self.hist_x_buffer[mid] + span])
            else:
                self.hist_region_needs_init = True
        else:
            self.hist_region.hide()
            self.hist_filter_plot_widget.hide()
            self.hist_btn_add_filter.hide()
            if hasattr(self, 'hist_region_2'):
                self.hist_region_2.hide()

    def toggle_hist_filter_2(self):
        if self.hist2_btn_filter.isChecked():
            self.hist2_region.show()
            self.hist2_filter_plot_widget.show()
            self.hist2_btn_add_filter.show()
            if getattr(self, 'second_filter_active', False) and hasattr(self, 'hist_region_2'):
                self.hist2_region_2.show()
            self.hist2_filter_ydata = []
            if getattr(self, 'second_filter_active', False):
                self.hist2_filter_ydata_2 = []
            self.hist2_filter_xdata = []
            self.hist2_filter_curve.setData([], [])
            if hasattr(self, 'hist_filter_curve_2'):
                self.hist2_filter_curve_2.setData([], [])
            
            import time
            self.hist2_filter_start_time = time.time()
            
            if hasattr(self, 'hist_x_buffer') and self.hist2_x_buffer is not None and len(self.hist2_x_buffer) > 0:
                mid = len(self.hist2_x_buffer) // 2
                span = (self.hist2_x_buffer[-1] - self.hist2_x_buffer[0]) * 0.1
                if span == 0: span = 1
                self.hist2_region.setRegion([self.hist2_x_buffer[mid] - span, self.hist2_x_buffer[mid] + span])
            else:
                self.hist2_region_needs_init = True
        else:
            self.hist2_region.hide()
            self.hist2_filter_plot_widget.hide()
            self.hist2_btn_add_filter.hide()
            if hasattr(self, 'hist_region_2'):
                self.hist2_region_2.hide()

    def update_histogram_plot(self, x_data, y_data):
        if self.hist_plot_curve:
            try:
                binwidth_ps = float(self.hist_binwidth_input.text())
                
                self.hist_data_buffer = y_data.flatten()
                self.hist_x_buffer = x_data.flatten() * 1e-12
                
                mode = self.hist_mode_combo.currentText()
                if mode == "Correlation" and len(self.hist_x_buffer) > 0 and self.hist_x_buffer[0] >= 0:
                    self.hist_x_buffer = self.hist_x_buffer - (len(self.hist_x_buffer) * (binwidth_ps * 1e-12) / 2)
                
                # Check for empty arrays to prevent pyqtgraph crashes
                if len(self.hist_x_buffer) == 0 or len(self.hist_data_buffer) == 0:
                    self.hist_plot_curve.setData([], [])
                else:
                    self.hist_plot_curve.setData(self.hist_x_buffer, self.hist_data_buffer)
                    
                    if hasattr(self, 'hist_btn_filter') and self.hist_btn_filter.isChecked():
                        if getattr(self, 'hist_region_needs_init', False) and len(self.hist_x_buffer) > 0:
                            mid = len(self.hist_x_buffer) // 2
                            span = (self.hist_x_buffer[-1] - self.hist_x_buffer[0]) * 0.1
                            if span == 0: span = 1
                            self.hist_region.setRegion([self.hist_x_buffer[mid] - span, self.hist_x_buffer[mid] + span])
                            self.hist_region_needs_init = False
                            
                        minX, maxX = self.hist_region.getRegion()
                        mask = (self.hist_x_buffer >= minX) & (self.hist_x_buffer <= maxX)
                        sum_val = np.sum(self.hist_data_buffer[mask])
                        
                        sum_val_2 = 0
                        if getattr(self, 'second_filter_active', False) and hasattr(self, 'hist_region_2'):
                            minX_2, maxX_2 = self.hist_region_2.getRegion()
                            mask_2 = (self.hist_x_buffer >= minX_2) & (self.hist_x_buffer <= maxX_2)
                            sum_val_2 = np.sum(self.hist_data_buffer[mask_2])
                        
                        import time
                        if not hasattr(self, 'hist_filter_start_time'):
                            self.hist_filter_start_time = time.time()
                            
                        elapsed = time.time() - self.hist_filter_start_time
                        
                        self.hist_filter_ydata.append(sum_val)
                        if getattr(self, 'second_filter_active', False) and hasattr(self, 'hist_filter_ydata_2'):
                            self.hist_filter_ydata_2.append(sum_val_2)
                        self.hist_filter_xdata.append(elapsed)
                        
                        if len(self.hist_filter_ydata) > 10000:
                            self.hist_filter_ydata = self.hist_filter_ydata[-10000:]
                            if getattr(self, 'second_filter_active', False) and hasattr(self, 'hist_filter_ydata_2'):
                                self.hist_filter_ydata_2 = self.hist_filter_ydata_2[-10000:]
                            self.hist_filter_xdata = self.hist_filter_xdata[-10000:]
                            
                        view_x_range = self.hist_filter_plot_widget.viewRange()[0]
                        current_window = view_x_range[1] - view_x_range[0]
                        if current_window < 1 or current_window > 100000:
                            current_window = 60
                            
                        if elapsed > current_window:
                            self.hist_filter_plot_widget.setXRange(elapsed - current_window, elapsed, padding=0)
                        else:
                            self.hist_filter_plot_widget.setXRange(0, current_window, padding=0)
                            
                        self.hist_filter_curve.setData(self.hist_filter_xdata, self.hist_filter_ydata)
                        if getattr(self, 'second_filter_active', False) and hasattr(self, 'hist_filter_curve_2') and hasattr(self, 'hist_filter_ydata_2'):
                            self.hist_filter_curve_2.setData(self.hist_filter_xdata, self.hist_filter_ydata_2)
            except Exception as e:
                logger.error(f"Error plotting histogram: {e}")

    def update_histogram_plot_2(self, x_data, y_data):
        if self.hist2_plot_curve:
            try:
                binwidth_ps = float(self.hist2_binwidth_input.text())
                
                self.hist2_data_buffer = y_data.flatten()
                self.hist_x_buffer = x_data.flatten() * 1e-12
                
                mode = self.hist2_mode_combo.currentText()
                if mode == "Correlation" and len(self.hist_x_buffer) > 0 and self.hist_x_buffer[0] >= 0:
                    self.hist_x_buffer = self.hist_x_buffer - (len(self.hist_x_buffer) * (binwidth_ps * 1e-12) / 2)
                
                # Check for empty arrays to prevent pyqtgraph crashes
                if len(self.hist_x_buffer) == 0 or len(self.hist2_data_buffer) == 0:
                    self.hist2_plot_curve.setData([], [])
                else:
                    self.hist2_plot_curve.setData(self.hist_x_buffer, self.hist2_data_buffer)
                    
                    if hasattr(self, 'hist_btn_filter') and self.hist2_btn_filter.isChecked():
                        if getattr(self, 'hist_region_needs_init', False) and len(self.hist_x_buffer) > 0:
                            mid = len(self.hist_x_buffer) // 2
                            span = (self.hist_x_buffer[-1] - self.hist_x_buffer[0]) * 0.1
                            if span == 0: span = 1
                            self.hist2_region.setRegion([self.hist_x_buffer[mid] - span, self.hist_x_buffer[mid] + span])
                            self.hist2_region_needs_init = False
                            
                        minX, maxX = self.hist2_region.getRegion()
                        mask = (self.hist_x_buffer >= minX) & (self.hist_x_buffer <= maxX)
                        sum_val = np.sum(self.hist2_data_buffer[mask])
                        
                        sum_val_2 = 0
                        if getattr(self, 'second_filter_active', False) and hasattr(self, 'hist_region_2'):
                            minX_2, maxX_2 = self.hist2_region_2.getRegion()
                            mask_2 = (self.hist_x_buffer >= minX_2) & (self.hist_x_buffer <= maxX_2)
                            sum_val_2 = np.sum(self.hist2_data_buffer[mask_2])
                        
                        import time
                        if not hasattr(self, 'hist_filter_start_time'):
                            self.hist2_filter_start_time = time.time()
                            
                        elapsed = time.time() - self.hist2_filter_start_time
                        
                        self.hist2_filter_ydata.append(sum_val)
                        if getattr(self, 'second_filter_active', False) and hasattr(self, 'hist_filter_ydata_2'):
                            self.hist2_filter_ydata_2.append(sum_val_2)
                        self.hist2_filter_xdata.append(elapsed)
                        
                        if len(self.hist2_filter_ydata) > 10000:
                            self.hist2_filter_ydata = self.hist2_filter_ydata[-10000:]
                            if getattr(self, 'second_filter_active', False) and hasattr(self, 'hist_filter_ydata_2'):
                                self.hist2_filter_ydata_2 = self.hist2_filter_ydata_2[-10000:]
                            self.hist2_filter_xdata = self.hist2_filter_xdata[-10000:]
                            
                        view_x_range = self.hist2_filter_plot_widget.viewRange()[0]
                        current_window = view_x_range[1] - view_x_range[0]
                        if current_window < 1 or current_window > 100000:
                            current_window = 60
                            
                        if elapsed > current_window:
                            self.hist2_filter_plot_widget.setXRange(elapsed - current_window, elapsed, padding=0)
                        else:
                            self.hist2_filter_plot_widget.setXRange(0, current_window, padding=0)
                            
                        self.hist2_filter_curve.setData(self.hist2_filter_xdata, self.hist2_filter_ydata)
                        if getattr(self, 'second_filter_active', False) and hasattr(self, 'hist_filter_curve_2') and hasattr(self, 'hist_filter_ydata_2'):
                            self.hist2_filter_curve_2.setData(self.hist2_filter_xdata, self.hist2_filter_ydata_2)
            except Exception as e:
                logger.error(f"Error plotting histogram: {e}")

    def toggle_histogram_play_pause(self):
        if self.hist_worker is None:
            self.start_histogram_measurement()
        else:
            self.pause_histogram_measurement()

    def toggle_histogram_play_pause_2(self):
        if self.hist2_worker is None:
            self.start_histogram_measurement_2()
        else:
            self.pause_histogram_measurement_2()

    def pause_histogram_measurement(self):
        if self.hist_worker:
            self.hist_worker.is_paused = not self.hist_worker.is_paused
            if self.hist_worker.is_paused:
                self.hist_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
                self.hist_btn_play_pause.setToolTip("Resume")
                self.hist_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
                self.hist_btn_play_pause.setToolTip("Resume")
                self.hist_btn_export.setEnabled(True)
            else:
                self.hist_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
                self.hist_btn_play_pause.setToolTip("Pause")
                self.hist_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
                self.hist_btn_play_pause.setToolTip("Pause")
                self.hist_btn_export.setEnabled(False)

    def pause_histogram_measurement_2(self):
        if self.hist2_worker:
            self.hist2_worker.is_paused = not self.hist2_worker.is_paused
            if self.hist2_worker.is_paused:
                self.hist2_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
                self.hist2_btn_play_pause.setToolTip("Resume")
                self.hist2_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
                self.hist2_btn_play_pause.setToolTip("Resume")
                self.hist2_btn_export.setEnabled(True)
            else:
                self.hist2_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
                self.hist2_btn_play_pause.setToolTip("Pause")
                self.hist2_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
                self.hist2_btn_play_pause.setToolTip("Pause")
                self.hist2_btn_export.setEnabled(False)

    def hist_toggle_zoom(self, checked):
        if checked:
            self.hist_plot_widget.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        else:
            self.hist_plot_widget.getViewBox().setMouseMode(pg.ViewBox.PanMode)

    def hist_toggle_zoom_2(self, checked):
        if checked:
            self.hist2_plot_widget.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        else:
            self.hist2_plot_widget.getViewBox().setMouseMode(pg.ViewBox.PanMode)

    def hist_force_auto_range(self):
        self.hist_plot_widget.enableAutoRange()

    def hist_force_auto_range_2(self):
        self.hist2_plot_widget.enableAutoRange()

    def on_hist_mode_changed(self):
        mode = self.hist_mode_combo.currentText()
        if mode == "Start-Stop":
            self.hist_n_values_input.setEnabled(False)
            if hasattr(self, 'lbl_hist_bins'):
                self.lbl_hist_bins.setEnabled(False)
        else:
            self.hist_n_values_input.setEnabled(True)
            if hasattr(self, 'lbl_hist_bins'):
                self.lbl_hist_bins.setEnabled(True)
                
        if hasattr(self, 'hist_btn_filter'):
            self.hist_btn_filter.show()

    def on_hist_mode_changed_2(self):
        mode = self.hist2_mode_combo.currentText()
        if mode == "Start-Stop":
            self.hist2_n_values_input.setEnabled(False)
            if hasattr(self, 'lbl_hist_bins'):
                self.lbl_hist_bins.setEnabled(False)
        else:
            self.hist2_n_values_input.setEnabled(True)
            if hasattr(self, 'lbl_hist_bins'):
                self.lbl_hist_bins.setEnabled(True)
                
        if hasattr(self, 'hist_btn_filter'):
            self.hist2_btn_filter.show()

    def quick_restart_histogram(self):
        if self.hist_worker:
            self.reset_histogram_measurement()
            self.start_histogram_measurement()


    def quick_restart_histogram_2(self):
        if self.hist2_worker:
            self.reset_histogram_measurement()
            self.start_histogram_measurement_2()


    def stop_histogram_measurement(self):
        if self.hist_worker:
            self.hist_worker.stop()
            self.hist_worker = None
        from PyQt6.QtWidgets import QStyle
        self.hist_btn_play_pause.setEnabled(True)
        self.hist_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.hist_btn_play_pause.setToolTip("Start")
        self.hist_btn_reset.setEnabled(True)
        self.hist_btn_stop.setEnabled(False)
        self.hist_btn_export.setEnabled(True)
        self.hist_binwidth_input.setEnabled(True)
        self.hist_start_combo.setEnabled(True)
        self.hist_click_combo.setEnabled(True)
        self.on_hist_mode_changed()
        self.set_other_tabs_enabled(True, 2)

    def stop_histogram_measurement_2(self):
        if self.hist2_worker:
            self.hist2_worker.stop()
            self.hist2_worker = None
        from PyQt6.QtWidgets import QStyle
        self.hist2_btn_play_pause.setEnabled(True)
        self.hist2_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.hist2_btn_play_pause.setToolTip("Start")
        self.hist2_btn_reset.setEnabled(True)
        self.hist2_btn_stop.setEnabled(False)
        self.hist2_btn_export.setEnabled(True)
        self.hist2_binwidth_input.setEnabled(True)
        self.hist2_start_combo.setEnabled(True)
        self.hist2_click_combo.setEnabled(True)
        self.on_hist_mode_changed_2()
        self.set_other_tabs_enabled(True, 3)

    def reset_histogram_measurement(self):
        if self.hist_worker:
            self.hist_worker.stop()
            self.old_workers.append(self.hist_worker)
            self.hist_worker = None
            
        self.hist_plot_widget.clear()
        self.hist_plot_widget.addItem(self.hist_region)
        if hasattr(self, 'hist_region_2'):
            self.hist_plot_widget.addItem(self.hist_region_2)
        if not self.hist_btn_filter.isChecked():
            self.hist_region.hide()
            if hasattr(self, 'hist_region_2'):
                self.hist_region_2.hide()
        self.hist_plot_curve = None
        self.hist_data_buffer = None
        self.hist_x_buffer = None
        
        self.hist_btn_play_pause.setEnabled(True)
        self.hist_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.hist_btn_play_pause.setToolTip("Start")
        self.hist_btn_reset.setEnabled(False)
        self.hist_btn_stop.setEnabled(False)
        self.hist_btn_export.setEnabled(False)
        
        self.hist_binwidth_input.setEnabled(True)
        self.hist_mode_combo.setEnabled(True)
        self.hist_start_combo.setEnabled(True)
        self.hist_click_combo.setEnabled(True)
        self.on_hist_mode_changed()
        
        self.set_other_tabs_enabled(True, 2)

    def reset_histogram_measurement_2(self):
        if self.hist2_worker:
            self.hist2_worker.stop()
            self.old_workers.append(self.hist2_worker)
            self.hist2_worker = None
            
        self.hist2_plot_widget.clear()
        self.hist2_plot_widget.addItem(self.hist2_region)
        if hasattr(self, 'hist_region_2'):
            self.hist2_plot_widget.addItem(self.hist2_region_2)
        if not self.hist2_btn_filter.isChecked():
            self.hist2_region.hide()
            if hasattr(self, 'hist_region_2'):
                self.hist2_region_2.hide()
        self.hist2_plot_curve = None
        self.hist2_data_buffer = None
        self.hist2_x_buffer = None
        
        self.hist2_btn_play_pause.setEnabled(True)
        self.hist2_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.hist2_btn_play_pause.setToolTip("Start")
        self.hist2_btn_reset.setEnabled(False)
        self.hist2_btn_stop.setEnabled(False)
        self.hist2_btn_export.setEnabled(False)
        
        self.hist2_binwidth_input.setEnabled(True)
        self.hist2_mode_combo.setEnabled(True)
        self.hist2_start_combo.setEnabled(True)
        self.hist2_click_combo.setEnabled(True)
        self.on_hist_mode_changed_2()
        
        self.set_other_tabs_enabled(True, 3)

    def on_histogram_worker_finished(self):
        self.hist_btn_play_pause.setEnabled(True)
        self.hist_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.hist_btn_play_pause.setToolTip("Start")
        self.hist_btn_reset.setEnabled(True)
        self.hist_btn_export.setEnabled(True)
        
        self.hist_binwidth_input.setEnabled(True)
        self.hist_mode_combo.setEnabled(True)
        self.hist_start_combo.setEnabled(True)
        self.hist_click_combo.setEnabled(True)
        self.on_hist_mode_changed()
        
        self.set_other_tabs_enabled(True, 2)
        self.hist_worker = None

    def on_histogram_worker_finished_2(self):
        self.hist2_btn_play_pause.setEnabled(True)
        self.hist2_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.hist2_btn_play_pause.setToolTip("Start")
        self.hist2_btn_reset.setEnabled(True)
        self.hist2_btn_export.setEnabled(True)
        
        self.hist2_binwidth_input.setEnabled(True)
        self.hist2_mode_combo.setEnabled(True)
        self.hist2_start_combo.setEnabled(True)
        self.hist2_click_combo.setEnabled(True)
        self.on_hist_mode_changed_2()
        
        self.set_other_tabs_enabled(True, 3)
        self.hist2_worker = None

    def export_histogram_data(self):
        if self.hist_data_buffer is None:
            QMessageBox.warning(self, "No Data", "There is no data to export.")
            return
            
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Histogram Data", "", "NumPy Files (*.npy);;All Files (*)"
        )
        if not file_path:
            return
            
        try:
            # We will save the x-axis and the histogram values
            data_to_save = np.column_stack([self.hist_x_buffer, self.hist_data_buffer])
            
            np.save(file_path, data_to_save)
            
            final_path = file_path if file_path.endswith('.npy') else file_path + '.npy'
            logger.info(f"Exported histogram data successfully to {final_path}")
            QMessageBox.information(self, "Export Successful", f"Data successfully saved to:\n{final_path}")
        except Exception as e:
            logger.error(f"Export Failed: {e}")
            QMessageBox.critical(self, "Export Failed", f"An error occurred while saving:\n{e}")

    def export_histogram_data_2(self):
        if self.hist2_data_buffer is None:
            QMessageBox.warning(self, "No Data", "There is no data to export.")
            return
            
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Histogram Data", "", "NumPy Files (*.npy);;All Files (*)"
        )
        if not file_path:
            return
            
        try:
            # We will save the x-axis and the histogram values
            data_to_save = np.column_stack([self.hist2_x_buffer, self.hist2_data_buffer])
            
            np.save(file_path, data_to_save)
            
            final_path = file_path if file_path.endswith('.npy') else file_path + '.npy'
            logger.info(f"Exported histogram data successfully to {final_path}")
            QMessageBox.information(self, "Export Successful", f"Data successfully saved to:\n{final_path}")
        except Exception as e:
            logger.error(f"Export Failed: {e}")
            QMessageBox.critical(self, "Export Failed", f"An error occurred while saving:\n{e}")

    def export_data(self):
        if not getattr(self, 'data_buffers', None) or not getattr(self, 'active_channels_list', None):
            QMessageBox.warning(self, "No Data", "There is no data to export.")
            return
            
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Plot Data", "", "NumPy Files (*.npy);;All Files (*)"
        )
        if not file_path:
            return
            
        try:
            n_bins = len(self.data_buffers[0])
            bins = np.arange(n_bins)
            data_to_save = np.column_stack([bins] + self.data_buffers)
            
            # np.save automatically appends .npy if not present
            np.save(file_path, data_to_save)
            
            # Ensure the success message shows the actual file path that was written
            final_path = file_path if file_path.endswith('.npy') else file_path + '.npy'
            logger.info(f"Exported data successfully to {final_path}")
            QMessageBox.information(self, "Export Successful", f"Data successfully saved to:\n{final_path}")
        except Exception as e:
            logger.error(f"Export Failed: {e}")
            QMessageBox.critical(self, "Export Failed", f"An error occurred while saving:\n{e}")

    def closeEvent(self, event):
        logger.info("Application is closing. Tearing down hardware and measurements...")
        
        if hasattr(self, 'old_workers'):
            for old_worker in self.old_workers:
                old_worker.force_teardown()
                    
        if self.worker:
            self.worker.force_teardown()
            
        if hasattr(self, 'hist_worker') and self.hist_worker:
            self.hist_worker.force_teardown()
            
        event.accept()
