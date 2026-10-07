import sys

file_path = "ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add imports if missing
if "QWidgetAction" not in content:
    content = content.replace("from PyQt6.QtWidgets import (", "from PyQt6.QtWidgets import (\n    QWidgetAction,\n    QMenu,")

# 1. Revert line edits from layout in build_histogram_tab
target1 = """        self.hist_btn_filter.clicked.connect(self.toggle_hist_filter)
        self.hist_btn_filter.hide()
        
        self.hist_filter_min_input = QLineEdit()
        self.hist_filter_min_input.setPlaceholderText("Min X")
        self.hist_filter_min_input.setMaximumWidth(80)
        self.hist_filter_min_input.hide()
        self.hist_filter_min_input.returnPressed.connect(self.update_hist_region_from_inputs)
        
        self.hist_filter_max_input = QLineEdit()
        self.hist_filter_max_input.setPlaceholderText("Max X")
        self.hist_filter_max_input.setMaximumWidth(80)
        self.hist_filter_max_input.hide()
        self.hist_filter_max_input.returnPressed.connect(self.update_hist_region_from_inputs)"""

replace1 = """        self.hist_btn_filter.clicked.connect(self.toggle_hist_filter)
        self.hist_btn_filter.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hist_btn_filter.customContextMenuRequested.connect(self.show_filter_context_menu)
        self.hist_btn_filter.hide()"""
content = content.replace(target1, replace1)

# 2. Revert adding them to controls
target2 = """        controls.addWidget(self.hist_btn_export)
        controls.addWidget(self.hist_btn_filter)
        controls.addWidget(self.hist_filter_min_input)
        controls.addWidget(self.hist_filter_max_input)"""

replace2 = """        controls.addWidget(self.hist_btn_export)
        controls.addWidget(self.hist_btn_filter)"""
content = content.replace(target2, replace2)

# 3. Revert the signal connection
target3 = """        self.hist_region = pg.LinearRegionItem(brush=(255, 255, 0, 50))
        self.hist_region.setZValue(10)
        self.hist_region.sigRegionChanged.connect(self.update_hist_filter_inputs_from_region)"""

replace3 = """        self.hist_region = pg.LinearRegionItem(brush=(255, 255, 0, 50))
        self.hist_region.setZValue(10)"""
content = content.replace(target3, replace3)

# 4. Remove the old methods and add show_filter_context_menu
target4 = """    def update_hist_filter_inputs_from_region(self):
        minX, maxX = self.hist_region.getRegion()
        self.hist_filter_min_input.setText(self.format_time_string(minX))
        self.hist_filter_max_input.setText(self.format_time_string(maxX))

    def update_hist_region_from_inputs(self):
        try:
            minX = self.parse_time_string(self.hist_filter_min_input.text())
            maxX = self.parse_time_string(self.hist_filter_max_input.text())
            self.hist_region.setRegion([minX, maxX])
        except ValueError:
            pass"""

replace4 = """    def show_filter_context_menu(self, pos):
        if not hasattr(self, 'hist_btn_filter') or not self.hist_btn_filter.isChecked():
            return
            
        menu = QMenu(self)
        
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        min_input = QLineEdit()
        min_input.setPlaceholderText("Min X")
        min_input.setMaximumWidth(80)
        
        max_input = QLineEdit()
        max_input.setPlaceholderText("Max X")
        max_input.setMaximumWidth(80)
        
        minX, maxX = self.hist_region.getRegion()
        min_input.setText(self.format_time_string(minX))
        max_input.setText(self.format_time_string(maxX))
        
        layout.addWidget(QLabel("Min:"))
        layout.addWidget(min_input)
        layout.addWidget(QLabel("Max:"))
        layout.addWidget(max_input)
        
        def on_enter():
            try:
                new_min = self.parse_time_string(min_input.text())
                new_max = self.parse_time_string(max_input.text())
                self.hist_region.setRegion([new_min, new_max])
                menu.close()
            except ValueError:
                pass
                
        min_input.returnPressed.connect(on_enter)
        max_input.returnPressed.connect(on_enter)
        
        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)
        menu.addAction(action)
        
        menu.exec(self.hist_btn_filter.mapToGlobal(pos))"""

content = content.replace(target4, replace4)

# 5. Remove `.show()` from toggle_hist_filter
target5 = """        if self.hist_btn_filter.isChecked():
            self.hist_region.show()
            self.hist_filter_plot_widget.show()
            self.hist_filter_min_input.show()
            self.hist_filter_max_input.show()"""

replace5 = """        if self.hist_btn_filter.isChecked():
            self.hist_region.show()
            self.hist_filter_plot_widget.show()"""
content = content.replace(target5, replace5)

# 6. Remove `.show()`/`.hide()` from toggle_hist_filter
target6 = """        if hasattr(self, 'hist_btn_filter'):
            self.hist_btn_filter.show()
            if self.hist_btn_filter.isChecked():
                self.hist_filter_min_input.show()
                self.hist_filter_max_input.show()
            else:
                self.hist_filter_min_input.hide()
                self.hist_filter_max_input.hide()"""

replace6 = """        if hasattr(self, 'hist_btn_filter'):
            self.hist_btn_filter.show()"""
content = content.replace(target6, replace6)

# 7. Remove `.hide()` from quick_restart_histogram and reset_histogram_measurement
target7 = """        if not self.hist_btn_filter.isChecked():
            self.hist_region.hide()
            self.hist_filter_min_input.hide()
            self.hist_filter_max_input.hide()"""

replace7 = """        if not self.hist_btn_filter.isChecked():
            self.hist_region.hide()"""
content = content.replace(target7, replace7)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
