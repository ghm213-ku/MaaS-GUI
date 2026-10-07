import sys

with open('ui/main_window.py', 'r') as f:
    content = f.read()

import_str = 'from hardware.histogram_worker import HistogramWorker\n'
new_import_str = import_str + 'from hardware.coincidences_worker import CoincidencesWorker\n'
content = content.replace(import_str, new_import_str)

reset_str = '        self.coinc_btn_reset.setEnabled(False)\n'
new_reset_str = reset_str + '        self.coinc_btn_reset.clicked.connect(self.reset_coincidences_measurement)\n'
content = content.replace(reset_str, new_reset_str)

methods_str = """
    def toggle_coincidences_play_pause(self):
        if self.coinc_worker is None:
            self.start_coincidences_measurement()
        else:
            self.pause_coincidences_measurement()

    def start_coincidences_measurement(self):
        channels = []
        for combo in self.coinc_combos:
            text = combo.currentText()
            if text:
                channels.append(int(text))
        
        if len(set(channels)) < 2:
            QMessageBox.warning(self, "Invalid Selection", "At least two unique channels must be selected.")
            return
            
        try:
            binwidth = int(self.coinc_binwidth_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Bin width must be an integer.")
            return

        self.coinc_plot_widget.clear()
        self.coinc_plot_curve = self.coinc_plot_widget.plot(pen='g')

        self.coinc_worker = CoincidencesWorker(
            channels=channels,
            user_name=self.login_username,
            binwidth=binwidth,
            auth_token=self.auth_token
        )
        self.coinc_worker.newDataReady.connect(self.update_coincidences_plot)
        self.coinc_worker.start()
        
        from PyQt6.QtWidgets import QStyle
        self.coinc_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.coinc_btn_play_pause.setToolTip("Pause")
        self.coinc_btn_reset.setEnabled(True)
        self.tabs.setTabEnabled(0, False)

    def pause_coincidences_measurement(self):
        if self.coinc_worker:
            self.coinc_worker.is_paused = not self.coinc_worker.is_paused
            from PyQt6.QtWidgets import QStyle
            if self.coinc_worker.is_paused:
                self.coinc_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
                self.coinc_btn_play_pause.setToolTip("Resume")
            else:
                self.coinc_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
                self.coinc_btn_play_pause.setToolTip("Pause")

    def reset_coincidences_measurement(self):
        if self.coinc_worker:
            self.coinc_worker.stop()
            self.old_workers.append(self.coinc_worker)
            self.coinc_worker = None
            
        self.coinc_plot_widget.clear()
        self.coinc_plot_curve = self.coinc_plot_widget.plot(pen='g')
        from PyQt6.QtWidgets import QStyle
        self.coinc_btn_play_pause.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.coinc_btn_play_pause.setToolTip("Start")
        self.coinc_btn_reset.setEnabled(False)
        self.tabs.setTabEnabled(0, True)

    def update_coincidences_plot(self, data):
        import numpy as np
        if not hasattr(self, 'coinc_ydata'):
            self.coinc_ydata = []
        self.coinc_ydata.append(np.sum(data))
        
        if len(self.coinc_ydata) > 100:
            self.coinc_ydata = self.coinc_ydata[-100:]
            
        self.coinc_plot_curve.setData(self.coinc_ydata)
"""

old_pass = "    def toggle_coincidences_play_pause(self):\n        pass # To be implemented with CoincidenceWorker"

content = content.replace(old_pass, methods_str.strip("\n"))

with open('ui/main_window.py', 'w') as f:
    f.write(content)
