import sys
import logging
import os
from pathlib import Path

import PyQt6

# Anaconda can expose Qt 5 plugins ahead of PyQt6's bundled Qt 6 plugins.
os.environ.setdefault(
    "QT_PLUGIN_PATH",
    str(Path(PyQt6.__file__).resolve().parent / "Qt6" / "plugins"),
)

from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QPalette
from PyQt6.QtCore import Qt

if __name__ == '__main__':
    # Setup robust logging for the entire application
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("maas_gui.log", mode='a'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting MaaS GUI Application")
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    light_palette = QPalette()
    light_palette.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    light_palette.setColor(QPalette.ColorRole.WindowText, QColor("#111111"))
    light_palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f7f7f7"))
    light_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    light_palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#111111"))
    light_palette.setColor(QPalette.ColorRole.Text, QColor("#111111"))
    light_palette.setColor(QPalette.ColorRole.Button, QColor("#fbfbfb"))
    light_palette.setColor(QPalette.ColorRole.ButtonText, QColor("#333333"))
    light_palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    light_palette.setColor(QPalette.ColorRole.Highlight, QColor("#dbeafe"))
    light_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#111111"))
    app.setPalette(light_palette)
    
    # Create a modern looking splash screen pixmap
    pixmap = QPixmap(500, 300)
    pixmap.fill(QColor("#ffffff"))
    
    painter = QPainter(pixmap)
    painter.fillRect(pixmap.rect(), QColor("#fbfbfb"))
    
    # Draw border
    pen = QPen(QColor("#e0e0e0"))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.drawRect(0, 0, 499, 299)
    
    # Draw Title
    painter.setPen(QColor("#111111"))
    painter.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "MaaS GUI")
    painter.end()
    
    # Show the splash screen
    splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
    splash.setFont(QFont("Segoe UI", 10))
    splash.showMessage("Loading components...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("#888888"))
    
    splash.show()
    app.processEvents() # Force the splash screen to render immediately
    
    # Perform the heavy imports while the splash screen is shown
    from ui.main_window import MainWindow
    
    force_mock = "testing" in sys.argv
    window = MainWindow(force_mock=force_mock)
    window.show()
    
    splash.finish(window)
    
    sys.exit(app.exec())
