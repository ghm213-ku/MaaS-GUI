import sys

file_path = "ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the method calls in histogram tab 2
content = content.replace("self.hist2_toggle_zoom", "self.hist_toggle_zoom_2")
content = content.replace("self.hist2_force_auto_range", "self.hist_force_auto_range_2")
content = content.replace("self.toggle_hist2_filter", "self.toggle_hist_filter_2") # not sure if this happened

# Wait, `toggle_hist_filter` became `toggle_hist2_filter`? 
# "self.hist_" -> "self.hist2_"
# "self.toggle_hist_filter" -> "self.toggle_hist2_filter"
content = content.replace("self.toggle_hist2_filter", "self.toggle_hist_filter_2")
content = content.replace("self.toggle_hist2_filter_2", "self.toggle_hist_filter_2") 
# in case it was replaced multiple times
content = content.replace("self.show_filter_context_menu_2", "self.show_filter_context_menu_2") # just to be safe

# The method definitions themselves:
# def hist_toggle_zoom_2(self
content = content.replace("def hist2_toggle_zoom_2(self", "def hist_toggle_zoom_2(self")
content = content.replace("def hist2_force_auto_range_2(self", "def hist_force_auto_range_2(self")
content = content.replace("def toggle_hist2_filter_2(self", "def toggle_hist_filter_2(self")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
