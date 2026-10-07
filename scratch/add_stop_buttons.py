import sys
import re

file_path = "ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# --- COUNTER TAB ---
# Add UI button
btn_reset_counter_str = """        self.btn_reset = QPushButton()
        self.btn_reset.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_reset.setToolTip("Reset Data")
        self.btn_reset.setEnabled(False)
        self.btn_reset.clicked.connect(self.reset_measurement)"""

btn_stop_counter_str = """        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.btn_stop.setToolTip("Stop Measurement (keep data)")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_measurement)"""

content = content.replace(btn_reset_counter_str, btn_reset_counter_str + "\n\n" + btn_stop_counter_str)
content = content.replace("        controls.addWidget(self.btn_reset)", "        controls.addWidget(self.btn_stop)\n        controls.addWidget(self.btn_reset)")

# Counter methods
stop_counter_func = """
    def stop_measurement(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        from PyQt6.QtWidgets import QStyle
        self.btn_play_pause.setEnabled(True)
        self.btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play_pause.setToolTip("Start")
        self.btn_reset.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_export.setEnabled(True)
        
        mode = self.mode_combo.currentText()
        if mode != "Repeating":
            self.binwidth_input.setEnabled(True)
            self.n_values_input.setEnabled(True)
        self.mode_combo.setEnabled(True)
        self.set_other_tabs_enabled(True, 1)
"""
content = content.replace("    def reset_measurement(self):", stop_counter_func + "\n    def reset_measurement(self):")

# Update start_measurement to enable stop button
content = content.replace("        self.btn_reset.setEnabled(True)\n        self.btn_export.setEnabled(False)", "        self.btn_reset.setEnabled(True)\n        self.btn_stop.setEnabled(True)\n        self.btn_export.setEnabled(False)")
content = content.replace("        self.btn_reset.setEnabled(False)\n        self.btn_export.setEnabled(False)", "        self.btn_reset.setEnabled(False)\n        self.btn_stop.setEnabled(False)\n        self.btn_export.setEnabled(False)")


# --- COINCIDENCES TAB ---
btn_reset_coinc_str = """        self.coinc_btn_reset = QPushButton()
        self.coinc_btn_reset.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.coinc_btn_reset.setToolTip("Reset Data")
        self.coinc_btn_reset.setEnabled(False)
        self.coinc_btn_reset.clicked.connect(self.reset_coincidences_measurement)"""

btn_stop_coinc_str = """        self.coinc_btn_stop = QPushButton()
        self.coinc_btn_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.coinc_btn_stop.setToolTip("Stop Measurement (keep data)")
        self.coinc_btn_stop.setEnabled(False)
        self.coinc_btn_stop.clicked.connect(self.stop_coincidences_measurement)"""

content = content.replace(btn_reset_coinc_str, btn_reset_coinc_str + "\n\n" + btn_stop_coinc_str)
content = content.replace("        controls.addWidget(self.coinc_btn_reset)", "        controls.addWidget(self.coinc_btn_stop)\n        controls.addWidget(self.coinc_btn_reset)")

stop_coinc_func = """
    def stop_coincidences_measurement(self):
        if self.coinc_worker:
            self.coinc_worker.stop()
            self.coinc_worker = None
        from PyQt6.QtWidgets import QStyle
        self.coinc_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.coinc_btn_play_pause.setToolTip("Start")
        self.coinc_btn_reset.setEnabled(True)
        self.coinc_btn_stop.setEnabled(False)
        self.set_other_tabs_enabled(True, 3)
"""
content = content.replace("    def reset_coincidences_measurement(self):", stop_coinc_func + "\n    def reset_coincidences_measurement(self):")

# Update coincidences start
content = content.replace("        self.coinc_btn_reset.setEnabled(True)\n        self.set_other_tabs_enabled(False, 3)", "        self.coinc_btn_reset.setEnabled(True)\n        self.coinc_btn_stop.setEnabled(True)\n        self.set_other_tabs_enabled(False, 3)")
content = content.replace("        self.coinc_btn_reset.setEnabled(False)\n        self.set_other_tabs_enabled(True, 3)", "        self.coinc_btn_reset.setEnabled(False)\n        self.coinc_btn_stop.setEnabled(False)\n        self.set_other_tabs_enabled(True, 3)")


# --- HISTOGRAMS TAB ---
btn_reset_hist_str = """        self.hist_btn_reset = QPushButton()
        self.hist_btn_reset.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.hist_btn_reset.setToolTip("Reset Data")
        self.hist_btn_reset.setEnabled(False)
        self.hist_btn_reset.clicked.connect(self.reset_histogram_measurement)"""

btn_stop_hist_str = """        self.hist_btn_stop = QPushButton()
        self.hist_btn_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.hist_btn_stop.setToolTip("Stop Measurement (keep data)")
        self.hist_btn_stop.setEnabled(False)
        self.hist_btn_stop.clicked.connect(self.stop_histogram_measurement)"""

content = content.replace(btn_reset_hist_str, btn_reset_hist_str + "\n\n" + btn_stop_hist_str)
content = content.replace("        controls.addWidget(self.hist_btn_reset)", "        controls.addWidget(self.hist_btn_stop)\n        controls.addWidget(self.hist_btn_reset)")

stop_hist_func = """
    def stop_histogram_measurement(self):
        if self.hist_worker:
            self.hist_worker.stop()
            self.hist_worker = None
        from PyQt6.QtWidgets import QStyle
        self.hist_btn_play_pause.setEnabled(True)
        self.hist_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.hist_btn_play_pause.setToolTip("Start")
        self.hist_btn_reset.setEnabled(True)
        self.hist_btn_stop.setEnabled(False)
        self.hist_btn_export.setEnabled(True)
        self.hist_binwidth_input.setEnabled(True)
        self.hist_start_combo.setEnabled(True)
        self.hist_click_combo.setEnabled(True)
        self.on_hist_mode_changed()
        self.set_other_tabs_enabled(True, 2)
"""
content = content.replace("    def reset_histogram_measurement(self):", stop_hist_func + "\n    def reset_histogram_measurement(self):")

content = content.replace("        self.hist_btn_reset.setEnabled(True)\n        self.hist_btn_export.setEnabled(False)", "        self.hist_btn_reset.setEnabled(True)\n        self.hist_btn_stop.setEnabled(True)\n        self.hist_btn_export.setEnabled(False)")
content = content.replace("        self.hist_btn_reset.setEnabled(False)\n        self.hist_btn_export.setEnabled(False)", "        self.hist_btn_reset.setEnabled(False)\n        self.hist_btn_stop.setEnabled(False)\n        self.hist_btn_export.setEnabled(False)")


with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
