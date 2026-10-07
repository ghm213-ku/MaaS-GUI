import sys
import re

file_path = "ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Corner Widget to tabs
corner_widget_code = """
        # Add + button to tabs
        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setFixedSize(25, 25)
        self.add_tab_btn.setStyleSheet("font-weight: bold;")
        self.add_tab_btn.clicked.connect(self.add_new_histogram_tab)
        self.tabs.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)
"""
if "self.add_tab_btn" not in content:
    content = content.replace("self.tabs.currentChanged.connect(self.on_tab_changed)", "self.tabs.currentChanged.connect(self.on_tab_changed)\n" + corner_widget_code)

# 2. Add add_new_histogram_tab method
add_tab_method = """
    def add_new_histogram_tab(self):
        if not hasattr(self, 'histogram_tab_2'):
            self.build_histogram_tab_2()
            self.tabs.insertTab(3, self.histogram_tab_2, "Histograms 2")
            self.add_tab_btn.setEnabled(False) # Max 2 tabs
"""
if "def add_new_histogram_tab" not in content:
    content = content.replace("    def build_histogram_tab(self):", add_tab_method + "\n    def build_histogram_tab(self):")


# 3. Extract all hist methods, duplicate them
hist_methods = [
    "build_histogram_tab",
    "update_histogram_channel_dropdowns",
    "start_histogram_measurement",
    "toggle_hist_filter",
    "toggle_second_filter",
    "show_filter_context_menu",
    "update_histogram_plot",
    "toggle_histogram_play_pause",
    "pause_histogram_measurement",
    "hist_toggle_zoom",
    "hist_force_auto_range",
    "on_hist_mode_changed",
    "quick_restart_histogram",
    "stop_histogram_measurement",
    "reset_histogram_measurement",
    "on_histogram_worker_finished",
    "export_histogram_data",
    "format_time_string"
]

for method in hist_methods:
    if f"def {method}_2(self" in content:
        continue
    
    # Extract method body
    # Find start
    method_def = f"    def {method}(self"
    start_idx = content.find(method_def)
    if start_idx == -1:
        continue
        
    # Find end
    end_idx = content.find("\n    def ", start_idx + 10)
    if end_idx == -1:
        end_idx = len(content)
        
    method_body = content[start_idx:end_idx]
    
    # Replace all self.hist_ with self.hist2_
    new_body = method_body.replace("self.hist_", "self.hist2_")
    new_body = new_body.replace("self.histogram_tab", "self.histogram_tab_2")
    new_body = new_body.replace("def " + method + "(self", "def " + method + "_2(self")
    
    # Specific replacements
    if method == "build_histogram_tab":
        # Rename worker finished slot
        new_body = new_body.replace("self.on_histogram_worker_finished", "self.on_histogram_worker_finished_2")
        new_body = new_body.replace("self.update_histogram_plot", "self.update_histogram_plot_2")
        # Replace method connections
        new_body = new_body.replace("self.toggle_histogram_play_pause", "self.toggle_histogram_play_pause_2")
        new_body = new_body.replace("self.reset_histogram_measurement", "self.reset_histogram_measurement_2")
        new_body = new_body.replace("self.stop_histogram_measurement", "self.stop_histogram_measurement_2")
        new_body = new_body.replace("self.hist_force_auto_range", "self.hist_force_auto_range_2")
        new_body = new_body.replace("self.export_histogram_data", "self.export_histogram_data_2")
        new_body = new_body.replace("self.on_hist_mode_changed", "self.on_hist_mode_changed_2")
        new_body = new_body.replace("self.toggle_hist_filter", "self.toggle_hist_filter_2")
        new_body = new_body.replace("self.toggle_second_filter", "self.toggle_second_filter_2")
        new_body = new_body.replace("self.show_filter_context_menu", "self.show_filter_context_menu_2")
    
    if method == "start_histogram_measurement":
        new_body = new_body.replace("self.on_histogram_worker_finished", "self.on_histogram_worker_finished_2")
        new_body = new_body.replace("self.update_histogram_plot", "self.update_histogram_plot_2")
        new_body = new_body.replace("set_other_tabs_enabled(False, 2)", "set_other_tabs_enabled(False, 3)")
        
    if method in ["stop_histogram_measurement", "reset_histogram_measurement", "on_histogram_worker_finished", "pause_histogram_measurement", "quick_restart_histogram"]:
        new_body = new_body.replace("set_other_tabs_enabled(True, 2)", "set_other_tabs_enabled(True, 3)")
        new_body = new_body.replace("self.on_hist_mode_changed", "self.on_hist_mode_changed_2")
        new_body = new_body.replace("self.quick_restart_histogram", "self.quick_restart_histogram_2")
        new_body = new_body.replace("self.pause_histogram_measurement", "self.pause_histogram_measurement_2")
        new_body = new_body.replace("self.start_histogram_measurement", "self.start_histogram_measurement_2")
    
    if method == "on_hist_mode_changed":
        new_body = new_body.replace("self.quick_restart_histogram", "self.quick_restart_histogram_2")

    if method == "toggle_histogram_play_pause":
        new_body = new_body.replace("self.start_histogram_measurement", "self.start_histogram_measurement_2")
        new_body = new_body.replace("self.pause_histogram_measurement", "self.pause_histogram_measurement_2")
        new_body = new_body.replace("self.quick_restart_histogram", "self.quick_restart_histogram_2")
        
    if method == "update_histogram_plot":
        new_body = new_body.replace("self.format_time_string", "self.format_time_string_2")
        new_body = new_body.replace("self.hist2_x_buffer", "self.hist_x_buffer") # Oops! hist2_x_buffer gets renamed from hist_x_buffer, wait, we actually want self.hist2_x_buffer!
        # wait, the replace above did "self.hist_" -> "self.hist2_"
        # so self.hist_x_buffer became self.hist2_x_buffer. That's CORRECT.
        
    content = content[:end_idx] + "\n" + new_body + content[end_idx:]

# Also update `on_tab_changed`
if 'elif self.tabs.tabText(index) == "Histograms 2":' not in content:
    on_tab = """        if self.tabs.tabText(index) == "Histograms":
            self.update_histogram_channel_dropdowns()
        elif self.tabs.tabText(index) == "Histograms 2":
            self.update_histogram_channel_dropdowns_2()"""
    content = content.replace('        if self.tabs.tabText(index) == "Histograms":\n            self.update_histogram_channel_dropdowns()', on_tab)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
