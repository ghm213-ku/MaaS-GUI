import sys

with open('ui/main_window.py', 'r') as f:
    content = f.read()

# 1. Add filter button to controls
export_btn_str = """        self.hist_btn_export.clicked.connect(self.export_histogram_data)"""
new_filter_btn = """        self.hist_btn_export.clicked.connect(self.export_histogram_data)
        
        self.hist_btn_filter = QPushButton("Filter")
        self.hist_btn_filter.setCheckable(True)
        self.hist_btn_filter.setToolTip("Toggle filter region")
        self.hist_btn_filter.clicked.connect(self.toggle_hist_filter)
        self.hist_btn_filter.hide()"""
content = content.replace(export_btn_str, new_filter_btn)

# 2. Add button to controls layout
controls_export_str = """        controls.addWidget(self.hist_btn_export)"""
new_controls_export = """        controls.addWidget(self.hist_btn_export)
        controls.addWidget(self.hist_btn_filter)"""
content = content.replace(controls_export_str, new_controls_export)

# 3. Add region and second plot
hist_plot_curve_str = """        self.hist_plot_curve = None
        
        layout.addWidget(self.hist_plot_widget)"""
new_plots = """        self.hist_plot_curve = None
        
        self.hist_region = pg.LinearRegionItem(brush=(255, 255, 0, 50))
        self.hist_region.setZValue(10)
        self.hist_region.hide()
        self.hist_plot_widget.addItem(self.hist_region)

        self.hist_filter_plot_widget = pg.PlotWidget()
        self.hist_filter_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.hist_filter_plot_widget.setLabel('bottom', 'Update Index')
        self.hist_filter_plot_widget.setLabel('left', 'Sum in Filter')
        self.hist_filter_plot_widget.hide()
        self.hist_filter_curve = self.hist_filter_plot_widget.plot(pen='y')
        
        self.hist_filter_ydata = []
        self.hist_filter_xdata = []
        
        layout.addWidget(self.hist_plot_widget)
        layout.addWidget(self.hist_filter_plot_widget)"""
content = content.replace(hist_plot_curve_str, new_plots)

# 4. Modify on_hist_mode_changed
on_hist_mode_changed_end = """        else:
            self.hist_start_combo.setEnabled(False)
            self.hist_click_combo.setEnabled(False)"""
new_mode_changed_end = """        else:
            self.hist_start_combo.setEnabled(False)
            self.hist_click_combo.setEnabled(False)
            
        if hasattr(self, 'hist_btn_filter'):
            if mode == "Correlation":
                self.hist_btn_filter.show()
            else:
                self.hist_btn_filter.hide()
                if self.hist_btn_filter.isChecked():
                    self.hist_btn_filter.setChecked(False)
                    self.toggle_hist_filter()"""
content = content.replace(on_hist_mode_changed_end, new_mode_changed_end)

# 5. Add toggle_hist_filter method
update_hist_def_str = """    def update_histogram_plot(self, x_data, y_data):"""
toggle_method = """    def toggle_hist_filter(self):
        if self.hist_btn_filter.isChecked():
            self.hist_region.show()
            self.hist_filter_plot_widget.show()
            self.hist_filter_ydata = []
            self.hist_filter_xdata = []
            self.hist_filter_curve.setData([], [])
            
            if hasattr(self, 'hist_x_buffer') and len(self.hist_x_buffer) > 0:
                mid = len(self.hist_x_buffer) // 2
                span = (self.hist_x_buffer[-1] - self.hist_x_buffer[0]) * 0.1
                if span == 0: span = 1
                self.hist_region.setRegion([self.hist_x_buffer[mid] - span, self.hist_x_buffer[mid] + span])
        else:
            self.hist_region.hide()
            self.hist_filter_plot_widget.hide()

    def update_histogram_plot(self, x_data, y_data):"""
content = content.replace(update_hist_def_str, toggle_method)

# 6. Add logic in update_histogram_plot
plot_set_data_str = """                    self.hist_plot_curve.setData(self.hist_x_buffer, self.hist_data_buffer)"""
new_plot_set_data = """                    self.hist_plot_curve.setData(self.hist_x_buffer, self.hist_data_buffer)
                    
                    if hasattr(self, 'hist_btn_filter') and self.hist_btn_filter.isChecked() and mode == "Correlation":
                        minX, maxX = self.hist_region.getRegion()
                        mask = (self.hist_x_buffer >= minX) & (self.hist_x_buffer <= maxX)
                        sum_val = np.sum(self.hist_data_buffer[mask])
                        
                        self.hist_filter_ydata.append(sum_val)
                        self.hist_filter_xdata.append(len(self.hist_filter_ydata))
                        
                        if len(self.hist_filter_ydata) > 1000:
                            self.hist_filter_ydata = self.hist_filter_ydata[-1000:]
                            self.hist_filter_xdata = list(range(self.hist_filter_xdata[-1000], self.hist_filter_xdata[-1000] + 1000))
                            
                        self.hist_filter_curve.setData(self.hist_filter_xdata, self.hist_filter_ydata)"""
content = content.replace(plot_set_data_str, new_plot_set_data)

with open('ui/main_window.py', 'w') as f:
    f.write(content)
