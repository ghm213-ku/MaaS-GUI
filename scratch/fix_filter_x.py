import re

file_path = "ui/main_window.py"
with open(file_path, "r") as f:
    content = f.read()

# 1. Change label from 'Update Index' to 'Time (s)'
content = content.replace(
    "self.hist_filter_plot_widget.setLabel('bottom', 'Update Index')",
    "self.hist_filter_plot_widget.setLabel('bottom', 'Time (s)')"
)

# 2. Add start_time initialization in toggle_hist_filter
toggle_target = """            self.hist_filter_xdata = []
            self.hist_filter_curve.setData([], [])"""
toggle_replace = """            self.hist_filter_xdata = []
            self.hist_filter_curve.setData([], [])
            
            import time
            self.hist_filter_start_time = time.time()"""
content = content.replace(toggle_target, toggle_replace)

# 3. Update update_histogram_plot
plot_target = """                        self.hist_filter_ydata.append(sum_val)
                        self.hist_filter_xdata.append(len(self.hist_filter_ydata))
                        
                        if len(self.hist_filter_ydata) > 1000:
                            self.hist_filter_ydata = self.hist_filter_ydata[-1000:]
                            self.hist_filter_xdata = list(range(self.hist_filter_xdata[-1000], self.hist_filter_xdata[-1000] + 1000))
                            
                        self.hist_filter_curve.setData(self.hist_filter_xdata, self.hist_filter_ydata)"""

plot_replace = """                        import time
                        if not hasattr(self, 'hist_filter_start_time'):
                            self.hist_filter_start_time = time.time()
                            
                        elapsed = time.time() - self.hist_filter_start_time
                        
                        self.hist_filter_ydata.append(sum_val)
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
content = content.replace(plot_target, plot_replace)


with open(file_path, "w") as f:
    f.write(content)
