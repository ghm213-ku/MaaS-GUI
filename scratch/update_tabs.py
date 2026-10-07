import sys

file_path = "ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add helper
if "def set_other_tabs_enabled" not in content:
    helper_code = """
    def set_other_tabs_enabled(self, enabled, current_index):
        for i in range(self.tabs.count()):
            if i != current_index:
                self.tabs.setTabEnabled(i, enabled)

    def on_tab_changed(self, index):"""
    content = content.replace("    def on_tab_changed(self, index):", helper_code)

content = content.replace("self.tabs.setTabEnabled(0, False) # Disable setup tab while running or paused", "self.set_other_tabs_enabled(False, 1) # Disable other tabs while running or paused")
content = content.replace("""        self.tabs.setTabEnabled(0, True)
        self.tabs.setTabEnabled(2, True)""", "        self.set_other_tabs_enabled(True, 1)")

# Histogram start
content = content.replace("""        self.tabs.setTabEnabled(0, False)
        self.tabs.setTabEnabled(1, False)""", "        self.set_other_tabs_enabled(False, 2)")

# Histogram reset
content = content.replace("""        self.tabs.setTabEnabled(0, True)
        self.tabs.setTabEnabled(1, True)""", "        self.set_other_tabs_enabled(True, 2)")

# Coincidences start
# It disables tab 0 only right now
content = content.replace("        self.tabs.setTabEnabled(0, False)", "        self.set_other_tabs_enabled(False, 3)")
content = content.replace("        self.tabs.setTabEnabled(0, True)", "        self.set_other_tabs_enabled(True, 3)")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
