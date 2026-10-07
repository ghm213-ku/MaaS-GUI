import sys
import re

file_path = "ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add `hist_btn_add_filter` button
target1 = """        self.hist_btn_filter.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hist_btn_filter.customContextMenuRequested.connect(self.show_filter_context_menu)
        self.hist_btn_filter.hide()"""

replace1 = """        self.hist_btn_filter.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hist_btn_filter.customContextMenuRequested.connect(self.show_filter_context_menu)
        self.hist_btn_filter.hide()
        
        self.hist_btn_add_filter = QPushButton("+")
        self.hist_btn_add_filter.setToolTip("Add second filter")
        self.hist_btn_add_filter.clicked.connect(self.toggle_second_filter)
        self.hist_btn_add_filter.setMaximumWidth(30)
        self.hist_btn_add_filter.hide()"""
content = content.replace(target1, replace1)

# 2. Add `hist_btn_add_filter` to layout
target2 = """        controls.addWidget(self.hist_btn_export)
        controls.addWidget(self.hist_btn_filter)"""
replace2 = """        controls.addWidget(self.hist_btn_export)
        controls.addWidget(self.hist_btn_filter)
        controls.addWidget(self.hist_btn_add_filter)"""
content = content.replace(target2, replace2)

# 3. Add `toggle_second_filter` method, update `show_filter_context_menu`
target3 = """    def show_filter_context_menu(self, pos):
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

replace3 = """    def toggle_second_filter(self):
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
        menu.exec(self.hist_btn_filter.mapToGlobal(pos))"""
content = content.replace(target3, replace3)

# 4. toggle_hist_filter updates
target4 = """    def toggle_hist_filter(self):
        if self.hist_btn_filter.isChecked():
            self.hist_region.show()
            self.hist_filter_plot_widget.show()
            self.hist_filter_ydata = []
            self.hist_filter_xdata = []
            self.hist_filter_curve.setData([], [])
            import time
            self.hist_filter_start_time = time.time()
        else:
            self.hist_region.hide()
            self.hist_filter_plot_widget.hide()
            
        if hasattr(self, 'hist_btn_filter'):
            self.hist_btn_filter.show()"""

replace4 = """    def toggle_hist_filter(self):
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
        else:
            self.hist_region.hide()
            self.hist_filter_plot_widget.hide()
            self.hist_btn_add_filter.hide()
            if hasattr(self, 'hist_region_2'):
                self.hist_region_2.hide()
            
        if hasattr(self, 'hist_btn_filter'):
            self.hist_btn_filter.show()"""
content = content.replace(target4, replace4)

# 5. `self.hist_plot_widget.clear()` in `start_histogram_measurement`
target5 = """        if self.hist_worker is None:
            self.hist_plot_widget.clear()
            self.hist_plot_curve = self.hist_plot_widget.plot(pen='b')
            self.hist_plot_widget.addItem(self.hist_region)
            if not self.hist_btn_filter.isChecked():
                self.hist_region.hide()
            self.hist_data_buffer = np.zeros(n_values)"""

replace5 = """        if self.hist_worker is None:
            self.hist_plot_widget.clear()
            self.hist_plot_curve = self.hist_plot_widget.plot(pen='b')
            self.hist_plot_widget.addItem(self.hist_region)
            if hasattr(self, 'hist_region_2'):
                self.hist_plot_widget.addItem(self.hist_region_2)
            if not self.hist_btn_filter.isChecked():
                self.hist_region.hide()
                if hasattr(self, 'hist_region_2'):
                    self.hist_region_2.hide()
            self.hist_data_buffer = np.zeros(n_values)"""
content = content.replace(target5, replace5)

# 6. `self.hist_plot_widget.clear()` in `reset_histogram_measurement`
target6 = """        self.hist_plot_widget.clear()
        self.hist_plot_widget.addItem(self.hist_region)
        if not self.hist_btn_filter.isChecked():
            self.hist_region.hide()
        self.hist_plot_curve = None"""

replace6 = """        self.hist_plot_widget.clear()
        self.hist_plot_widget.addItem(self.hist_region)
        if hasattr(self, 'hist_region_2'):
            self.hist_plot_widget.addItem(self.hist_region_2)
        if not self.hist_btn_filter.isChecked():
            self.hist_region.hide()
            if hasattr(self, 'hist_region_2'):
                self.hist_region_2.hide()
        self.hist_plot_curve = None"""
content = content.replace(target6, replace6)

# 7. Updating data in `update_histogram_plot`
target7 = """                            self.hist_filter_ydata.append(sum_val)
                            self.hist_filter_xdata.append(elapsed)
                            
                            if len(self.hist_filter_ydata) > 10000:
                                self.hist_filter_ydata = self.hist_filter_ydata[-10000:]
                                self.hist_filter_xdata = self.hist_filter_xdata[-10000:]
                                
                            view_x_range = self.hist_filter_plot_widget.viewRange()[0]
                            current_window = view_x_range[1] - view_x_range[0]
                            if current_window < 1 or current_window > 100000:
                                current_window = 60
                                
                            if elapsed > current_window:
                                self.hist_filter_plot_widget.setXRange(elapsed - current_window, elapsed, padding=0)
                            else:
                                self.hist_filter_plot_widget.setXRange(0, current_window, padding=0)
                                
                            self.hist_filter_curve.setData(self.hist_filter_xdata, self.hist_filter_ydata)"""

replace7 = """                            self.hist_filter_ydata.append(sum_val)
                            self.hist_filter_xdata.append(elapsed)
                            
                            has_f2 = getattr(self, 'second_filter_active', False) and hasattr(self, 'hist_region_2')
                            if has_f2:
                                minX2, maxX2 = self.hist_region_2.getRegion()
                                mask2 = (self.hist_x_buffer >= minX2) & (self.hist_x_buffer <= maxX2)
                                sum_val2 = np.sum(self.hist_data_buffer[mask2])
                                self.hist_filter_ydata_2.append(sum_val2)
                            
                            if len(self.hist_filter_ydata) > 10000:
                                self.hist_filter_ydata = self.hist_filter_ydata[-10000:]
                                self.hist_filter_xdata = self.hist_filter_xdata[-10000:]
                                if has_f2:
                                    self.hist_filter_ydata_2 = self.hist_filter_ydata_2[-10000:]
                                
                            view_x_range = self.hist_filter_plot_widget.viewRange()[0]
                            current_window = view_x_range[1] - view_x_range[0]
                            if current_window < 1 or current_window > 100000:
                                current_window = 60
                                
                            if elapsed > current_window:
                                self.hist_filter_plot_widget.setXRange(elapsed - current_window, elapsed, padding=0)
                            else:
                                self.hist_filter_plot_widget.setXRange(0, current_window, padding=0)
                                
                            self.hist_filter_curve.setData(self.hist_filter_xdata, self.hist_filter_ydata)
                            if has_f2 and hasattr(self, 'hist_filter_curve_2'):
                                if len(self.hist_filter_xdata) == len(self.hist_filter_ydata_2):
                                    self.hist_filter_curve_2.setData(self.hist_filter_xdata, self.hist_filter_ydata_2)"""
content = content.replace(target7, replace7)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
