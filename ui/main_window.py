import numpy as np
# pyrefly: ignore [missing-import]
import pyqtgraph as pg
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox)

from hardware.worker import CountRateWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Swabian Count Rate Monitor")
        self.resize(800, 600)
        self.worker = None
        
        # --- 1. UI Setup ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Control Panel
        control_layout = QHBoxLayout()
        
        self.channel_input = QLineEdit("1, 2")
        self.channel_input.setPlaceholderText("Comma separated channels (e.g. 1, 2)")
        
        self.btn_start = QPushButton("Start")
        self.btn_start.clicked.connect(self.start_measurement)
        
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_measurement)
        
        control_layout.addWidget(QLabel("Channels:"))
        control_layout.addWidget(self.channel_input)
        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_stop)
        
        layout.addLayout(control_layout)
        
        # Plotting Area using PyQtGraph
        self.plot_widget = pg.PlotWidget(title="Count Rate Time Series")
        self.plot_widget.setLabel('left', 'Count Rate', units='cps')
        self.plot_widget.setLabel('bottom', 'Time (frames)')
        self.plot_widget.addLegend()
        layout.addWidget(self.plot_widget)
        
        # Data storage for plotting
        self.history_length = 200
        self.plot_curves = []
        self.data_buffers = []

    def start_measurement(self):
        # Parse channels from user input
        try:
            channels_str = self.channel_input.text().split(',')
            channels = [int(c.strip()) for c in channels_str]
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid integers separated by commas.")
            return

        # Prepare plot curves for the selected channels
        self.plot_widget.clear()
        self.plot_curves = []
        self.data_buffers = [np.zeros(self.history_length) for _ in channels]
        
        colors = ['r', 'g', 'b', 'c', 'm', 'y']
        for i, ch in enumerate(channels):
            pen = pg.mkPen(color=colors[i % len(colors)], width=2)
            curve = self.plot_widget.plot(pen=pen, name=f"Channel {ch}")
            self.plot_curves.append(curve)

        # Initialize and start the background thread
        self.worker = CountRateWorker(channels)
        
        # CONNECT SIGNAL TO SLOT: 
        # When worker emits newDataReady, execute self.update_plot
        self.worker.newDataReady.connect(self.update_plot)
        
        self.worker.start()
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.channel_input.setEnabled(False)

    def update_plot(self, rates):
        """
        This slot runs on the main GUI thread. 
        It receives the Numpy array 'rates' from the worker thread.
        """
        for i, rate in enumerate(rates):
            # Shift data to the left to create a scrolling effect
            self.data_buffers[i][:-1] = self.data_buffers[i][1:]
            self.data_buffers[i][-1] = rate
            
            # Update the PyQtGraph curve
            self.plot_curves[i].setData(self.data_buffers[i])

    def stop_measurement(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
            
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.channel_input.setEnabled(True)

    def closeEvent(self, event):
        # Ensure hardware is freed if the user closes the window while running
        self.stop_measurement()
        event.accept()
