import numpy as np
import requests
import json
import logging

logger = logging.getLogger(__name__)

# pyrefly: ignore [missing-import]
import pyqtgraph as pg
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QMessageBox,
                             QTabWidget, QGridLayout, QScrollArea, QCheckBox,
                             QFrame, QLineEdit, QDialog, QFormLayout, QSizePolicy, QComboBox)
from PyQt6.QtGui import QDoubleValidator, QIntValidator
from PyQt6.QtCore import Qt, pyqtSignal

from hardware.worker import CountRateWorker

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
            logger.info(f"Updated Channel {self.channel_id} settings: Trigger={t}V, Delay={d}ps")
            self.trigger_val = t
            self.delay_val = d
            self.lbl_trig.setText(f"{t}V")
            self.lbl_dly.setText(f"{d}ps")
            
    def set_booked_by(self, user_name, is_current_user):
        self.booked_by = user_name
        self.is_current_user = is_current_user
        if is_current_user:
            self.is_active = True
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
            logger.info(f"Channel {self.channel_id} toggled to {'active' if self.is_active else 'inactive'}")
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Swabian Count Rate Monitor")
        self.resize(1000, 700)
        self.worker = None
        
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
        
        # Central widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Build Tabs
        self.build_channels_setup_tab()
        self.build_counter_tab()
        
        # Add to TabWidget
        self.tabs.addTab(self.setup_tab, "Channels Setup")
        self.tabs.addTab(self.counter_tab, "Counter")

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
        user_layout.addWidget(QLabel("Duration (mins):"))
        self.duration_input = QLineEdit("60")
        self.duration_input.setFixedWidth(60)
        self.duration_input.setStyleSheet("padding: 4px; border: 1px solid #ccc; border-radius: 4px;")
        self.duration_input.setValidator(QIntValidator(1, 10000))
        user_layout.addWidget(self.duration_input)
        
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
        try:
            resp = requests.get("http://localhost:8000/api/v1/channels", timeout=2)
            if resp.status_code == 200:
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

    def build_counter_tab(self):
        self.counter_tab = QWidget()
        layout = QVBoxLayout(self.counter_tab)
        
        # Controls
        controls = QHBoxLayout()
        
        self.btn_start = QPushButton()
        self.btn_start.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_start.setToolTip("Start")
        self.btn_start.clicked.connect(self.start_measurement)
        
        self.btn_pause = QPushButton()
        self.btn_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.btn_pause.setToolTip("Pause")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.pause_measurement)

        self.btn_reset = QPushButton()
        self.btn_reset.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_reset.setToolTip("Reset Data")
        self.btn_reset.setEnabled(False)
        self.btn_reset.clicked.connect(self.reset_measurement)
        
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
        
        controls.addWidget(self.btn_start)
        controls.addWidget(self.btn_pause)
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
        controls.addWidget(QLabel("Bins:"))
        controls.addWidget(self.n_values_input)
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
        # Verify Backend Health
        try:
            health_resp = requests.get("http://localhost:8000/health", timeout=2)
            if health_resp.status_code != 200 or health_resp.json().get("status") != "healthy":
                QMessageBox.critical(self, "Backend Error", f"MaaS backend is not healthy.\nStatus Code: {health_resp.status_code}")
                return
        except Exception as e:
            QMessageBox.critical(self, "Backend Offline", f"Could not connect to the MaaS backend.\nPlease ensure it is running.\n\nDetails: {e}")
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

        # Initialize plot curves only if they don't exist (i.e. not resuming from pause)
        if not self.plot_curves:
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
                
            try:
                duration_minutes = int(self.duration_input.text())
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Please enter a valid number for duration.")
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
            
            self.worker = CountRateWorker(channels, user_name, binwidth, n_values, duration_minutes, refresh_rate, mode=mode)
            
            if self.worker.booking_error:
                QMessageBox.critical(self, "Booking Failed", self.worker.booking_error)
                self.worker = None
                return
                
            self.worker.newDataReady.connect(self.update_plot)
            self.worker.start()
            logger.info(f"Measurement started successfully for user {user_name} on channels {channels} with binwidth={binwidth}, n_values={n_values}, duration={duration_minutes}m, refresh={refresh_rate}Hz")
        else:
            self.worker.is_paused = False
            logger.info("Measurement resumed from pause.")
        
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_reset.setEnabled(False)
        self.binwidth_input.setEnabled(False)
        self.n_values_input.setEnabled(False)
        self.mode_combo.setEnabled(False)
        self.tabs.setTabEnabled(0, False) # Disable setup tab while running or paused

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

    def pause_measurement(self):
        if self.worker:
            self.worker.is_paused = True
            logger.info("Measurement paused by user.")
            
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_reset.setEnabled(True)

    def reset_measurement(self):
        if self.worker:
            logger.info("Resetting/stopping measurement by user.")
            self.worker.stop()
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
        
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_reset.setEnabled(False)
        self.btn_export.setEnabled(False)
        
        mode = self.mode_combo.currentText()
        if mode != "Repeating":
            self.binwidth_input.setEnabled(True)
            self.n_values_input.setEnabled(True)
        self.mode_combo.setEnabled(True)
        
        self.tabs.setTabEnabled(0, True)

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
        # Ensure hardware is freed if the user closes the window while running
        if self.worker:
            self.worker.force_teardown()
            # Wait for the background thread to exit cleanly
            self.worker.wait(1000) 
        event.accept()
