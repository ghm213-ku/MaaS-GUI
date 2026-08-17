import sys
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QPen
from PyQt6.QtCore import Qt

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
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
    
    window = MainWindow()
    window.show()
    
    splash.finish(window)
    
    sys.exit(app.exec())
