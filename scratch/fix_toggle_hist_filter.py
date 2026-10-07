import sys

file_path = "ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """    def toggle_hist_filter(self):
        if self.hist_btn_filter.isChecked():
            self.hist_region.show()
            self.hist_filter_plot_widget.show()
            self.hist_filter_ydata = []
            self.hist_filter_xdata = []
            self.hist_filter_curve.setData([], [])
            
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
            
        if hasattr(self, 'hist_btn_filter'):
            self.hist_btn_filter.show()"""

replace = """    def toggle_hist_filter(self):
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
            
        if hasattr(self, 'hist_btn_filter'):
            self.hist_btn_filter.show()"""

content = content.replace(target, replace)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
