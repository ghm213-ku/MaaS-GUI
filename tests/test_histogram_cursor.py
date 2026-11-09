"""Histogram tabs show a green cursor line with the nearest bin's time and counts."""
import numpy as np
import pyqtgraph as pg
import pytest
from PyQt6.QtCore import QPointF

from ui.main_window import HistogramCursor, MainWindow


def test_cursor_reports_nearest_bin(qtbot):
    plot = pg.PlotWidget()
    qtbot.addWidget(plot)
    plot.resize(600, 400)
    plot.show()
    qtbot.waitExposed(plot)
    x = np.array([0.0, 1e-9, 2e-9, 3e-9])
    y = np.array([5, 7, 42, 3])
    cursor = HistogramCursor(plot, lambda: (x, y))
    plot.setXRange(0, 3e-9, padding=0)
    plot.setYRange(0, 50, padding=0)

    cursor.mouse_moved(plot.plotItem.vb.mapViewToScene(QPointF(2.1e-9, 20)))

    assert cursor.v_line.value() == pytest.approx(2.1e-9, rel=1e-2)
    html = cursor.label.textItem.toHtml()
    assert "Counts: 42" in html
    assert "2 ns" in html


def test_cursor_ignores_missing_data(qtbot):
    plot = pg.PlotWidget()
    qtbot.addWidget(plot)
    cursor = HistogramCursor(plot, lambda: (None, None))
    cursor.mouse_moved(plot.plotItem.vb.mapViewToScene(QPointF(0, 0)))  # must not raise


@pytest.mark.parametrize("tab", ["hist", "hist2"])
def test_histogram_tabs_have_cursor_after_clear(qtbot, tab):
    window = MainWindow()
    qtbot.addWidget(window)
    if tab == "hist2":
        window.build_histogram_tab_2()
    plot = getattr(window, f"{tab}_plot_widget")
    cursor = getattr(window, f"{tab}_cursor")

    plot.clear()
    cursor.attach()

    assert cursor.v_line in plot.plotItem.items
    assert cursor.label in plot.plotItem.items
