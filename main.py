import sys
import logging
import os
from pathlib import Path

import PyQt6

# True when running from the packaged executable built by PyInstaller.
FROZEN = getattr(sys, "frozen", False)

# Anaconda can expose Qt 5 plugins ahead of PyQt6's bundled Qt 6 plugins.
# The packaged build ships its own plugins and configures them itself.
if not FROZEN:
    os.environ.setdefault(
        "QT_PLUGIN_PATH",
        str(Path(PyQt6.__file__).resolve().parent / "Qt6" / "plugins"),
    )

from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QPalette
from PyQt6.QtCore import Qt, QtMsgType, qInstallMessageHandler


def _default_log_file():
    """Log next to the source when run as a script; in a writable per-user
    folder (%LOCALAPPDATA%\\MaaS-GUI) when run as the packaged executable."""
    if not FROZEN:
        return "maas_gui.log"
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaaS-GUI"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "maas_gui.log")


LOG_FILE = _default_log_file()


def install_crash_logging(log_file=LOG_FILE):
    """Route every error we can catch into the log, with tracebacks.

    - Uncaught Python exceptions (main thread, Qt slots, worker threads) are
      logged with their full traceback instead of silently killing the app.
    - Qt's own warnings/fatal messages (e.g. "QThread: Destroyed while thread
      is still running") go through the logger.
    - faulthandler dumps the Python stack of every thread to the log if the
      process dies from a native crash (abort, segfault).
    """
    import faulthandler
    import threading

    log = logging.getLogger("crash")

    def excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

    def thread_excepthook(args):
        log.critical(
            "Uncaught exception in thread %s",
            getattr(args.thread, "name", "?"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook

    qt_levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }
    qt_log = logging.getLogger("qt")

    def qt_message_handler(msg_type, context, message):
        level = qt_levels.get(msg_type, logging.WARNING)
        where = ""
        if context is not None and context.file:
            where = f" ({context.file}:{context.line}, {context.function})"
        qt_log.log(level, "%s%s", message, where)
        if msg_type == QtMsgType.QtFatalMsg:
            # Qt aborts right after this; make sure the stacks are on disk.
            for handler in logging.getLogger().handlers:
                handler.flush()
            faulthandler.dump_traceback(file=_fault_file, all_threads=True)

    qInstallMessageHandler(qt_message_handler)

    # Keep the file open for the life of the process: faulthandler writes to
    # its file descriptor directly when the interpreter is crashing.
    global _fault_file
    _fault_file = open(log_file, "a", buffering=1, encoding="utf-8")
    faulthandler.enable(file=_fault_file, all_threads=True)


_fault_file = None

if __name__ == '__main__':
    # Setup robust logging for the entire application
    handlers = [logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')]
    # A windowed executable has no console (sys.stdout is None).
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    logger = logging.getLogger(__name__)
    install_crash_logging()
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
    
    # Test data is only used when explicitly requested with -testing;
    # otherwise all data comes from the MaaS backend.
    force_mock = any(arg in ("-testing", "--testing") for arg in sys.argv[1:])
    if force_mock:
        logger.info("Testing mode enabled: using generated test data instead of MaaS")
    window = MainWindow(force_mock=force_mock)
    window.show()
    
    splash.finish(window)
    
    sys.exit(app.exec())
