import sys

file_path = "ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add line edits
target1 = """        self.hist_btn_filter.clicked.connect(self.toggle_hist_filter)
        self.hist_btn_filter.hide()"""

replace1 = """        self.hist_btn_filter.clicked.connect(self.toggle_hist_filter)
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

content = content.replace(target1, replace1)

# 2. Add to controls
target2 = """        controls.addWidget(self.hist_btn_export)
        controls.addWidget(self.hist_btn_filter)"""

replace2 = """        controls.addWidget(self.hist_btn_export)
        controls.addWidget(self.hist_btn_filter)
        controls.addWidget(self.hist_filter_min_input)
        controls.addWidget(self.hist_filter_max_input)"""

content = content.replace(target2, replace2)

# 3. Add signal to hist_region
target3 = """        self.hist_region = pg.LinearRegionItem(brush=(255, 255, 0, 50))
        self.hist_region.setZValue(10)"""

replace3 = """        self.hist_region = pg.LinearRegionItem(brush=(255, 255, 0, 50))
        self.hist_region.setZValue(10)
        self.hist_region.sigRegionChanged.connect(self.update_hist_filter_inputs_from_region)"""

content = content.replace(target3, replace3)

# 4. Add methods
target4 = """    def toggle_hist_filter(self):"""

replace4 = """    def update_hist_filter_inputs_from_region(self):
        minX, maxX = self.hist_region.getRegion()
        self.hist_filter_min_input.setText(f"{minX:.2f}")
        self.hist_filter_max_input.setText(f"{maxX:.2f}")

    def update_hist_region_from_inputs(self):
        try:
            minX = float(self.hist_filter_min_input.text())
            maxX = float(self.hist_filter_max_input.text())
            self.hist_region.setRegion([minX, maxX])
        except ValueError:
            pass

    def toggle_hist_filter(self):"""

content = content.replace(target4, replace4)

# 5. Show/Hide in toggle_hist_filter
target5 = """        if self.hist_btn_filter.isChecked():
            self.hist_region.show()
            self.hist_filter_plot_widget.show()"""

replace5 = """        if self.hist_btn_filter.isChecked():
            self.hist_region.show()
            self.hist_filter_plot_widget.show()
            self.hist_filter_min_input.show()
            self.hist_filter_max_input.show()"""

content = content.replace(target5, replace5)

target6 = """        if hasattr(self, 'hist_btn_filter'):
            self.hist_btn_filter.show()"""

replace6 = """        if hasattr(self, 'hist_btn_filter'):
            self.hist_btn_filter.show()
            if self.hist_btn_filter.isChecked():
                self.hist_filter_min_input.show()
                self.hist_filter_max_input.show()
            else:
                self.hist_filter_min_input.hide()
                self.hist_filter_max_input.hide()"""

content = content.replace(target6, replace6)

# 6. Hide in quick_restart_histogram and reset_histogram_measurement
# Wait, in reset_histogram_measurement, we do:
#         if not self.hist_btn_filter.isChecked():
#             self.hist_region.hide()
# We should probably make sure the line edits are hidden if the filter is not checked.
# The toggle_hist_filter is the main place, but let's also update quick_restart_histogram
target7 = """        if not self.hist_btn_filter.isChecked():
            self.hist_region.hide()"""
replace7 = """        if not self.hist_btn_filter.isChecked():
            self.hist_region.hide()
            self.hist_filter_min_input.hide()
            self.hist_filter_max_input.hide()"""
content = content.replace(target7, replace7)


with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
