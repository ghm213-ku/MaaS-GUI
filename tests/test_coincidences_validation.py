import pytest
from PyQt6.QtWidgets import QMessageBox
from ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def mock_all_network(mocker):
    """Ensure no real network calls occur during UI validation tests."""
    mock_get = mocker.patch("requests.Session.get")
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"channels": []}
    mock_get.return_value = mock_resp
    mocker.patch("atexit.register")
    return mock_get


def coinc_kwargs(fake_workers):
    """Keyword arguments the window passed to the (fake) CoincidencesWorker."""
    return fake_workers.coincidences.call_args.kwargs


# =========================================================================
# 1. Channels Setup Corner Cases
# =========================================================================

def test_validation_no_channels_selected_in_setup(qtbot, mocker):
    """When user has selected no channels in the Channels Setup tab, alert user."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: []
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText("1, 2")
    window.start_coincidences_measurement()

    assert mock_warn.called
    title, text = mock_warn.call_args[0][1], mock_warn.call_args[0][2]
    assert "No Channels" in title
    assert "Channels Setup" in text
    assert window.coinc_worker is None


# =========================================================================
# 2. Coincidence Window Corner Cases
# =========================================================================

@pytest.mark.parametrize("invalid_window", ["", "   ", "abc", "1.5", "1e3", "0", "-100", "-1"])
def test_validation_invalid_coincidence_window(qtbot, mocker, invalid_window):
    """Coincidence window must be a strictly positive integer."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText("1, 2")
    window.coinc_binwidth_input.setText(invalid_window)
    window.start_coincidences_measurement()

    assert mock_warn.called
    assert "Invalid Input" in mock_warn.call_args[0][1]
    assert "positive integer" in mock_warn.call_args[0][2].lower()
    assert window.coinc_worker is None


def test_validation_coincidence_window_with_whitespace(qtbot, fake_workers):
    """Coincidence window with leading/trailing whitespace should be parsed cleanly."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2]

    window.coinc_boxes[0].setText("1, 2")
    window.coinc_binwidth_input.setText("   2500   ")
    window.start_coincidences_measurement()

    assert coinc_kwargs(fake_workers)["coincidence_window"] == 2500
    window.coinc_worker.start.assert_called_once()


# =========================================================================
# 3. Comma-Separated Channel Format Corner Cases
# =========================================================================

@pytest.mark.parametrize("empty_input", ["", "   ", "\t", "\n"])
def test_validation_empty_channel_box(qtbot, mocker, empty_input):
    """Empty or whitespace-only boxes should be rejected with a format warning."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText(empty_input)
    window.start_coincidences_measurement()

    assert mock_warn.called
    assert "Invalid Format" in mock_warn.call_args[0][1]
    assert window.coinc_worker is None


@pytest.mark.parametrize("malformed_input", [
    "1, 2,",       # Trailing comma
    ", 1, 2",      # Leading comma
    "1,, 2",       # Double comma
    "1,  , 2",     # Double comma with spaces
    ",",           # Single comma
    ",,,",         # Multiple commas only
])
def test_validation_malformed_commas(qtbot, mocker, malformed_input):
    """Lists with empty entries between or around commas should be rejected."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText(malformed_input)
    window.start_coincidences_measurement()

    assert mock_warn.called
    assert "Invalid Format" in mock_warn.call_args[0][1]
    assert "Malformed" in mock_warn.call_args[0][2]
    assert window.coinc_worker is None


@pytest.mark.parametrize("non_int_input", [
    "1, abc",
    "one, two",
    "1, 2.5",
    "1, 2e0",
    "1, #2",
    "1, 2; 3",    # Semicolon instead of comma
])
def test_validation_non_integer_tokens(qtbot, mocker, non_int_input):
    """Non-integer tokens should be rejected."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText(non_int_input)
    window.start_coincidences_measurement()

    assert mock_warn.called
    assert "Invalid Format" in mock_warn.call_args[0][1]
    assert "must be integer numbers" in mock_warn.call_args[0][2]
    assert window.coinc_worker is None


def test_validation_whitespace_around_numbers(qtbot, fake_workers):
    """Padded spaces around numbers (e.g. ' 1 ,  2 , 3 ') should parse cleanly."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]

    window.coinc_boxes[0].setText("   1   ,   2   ,   3   ")
    window.start_coincidences_measurement()

    assert coinc_kwargs(fake_workers)["coincidences"] == [[1, 2, 3]]
    window.coinc_worker.start.assert_called_once()


# =========================================================================
# 4. Group Size and Duplicate Channel Corner Cases
# =========================================================================

def test_validation_single_channel_rejected(qtbot, mocker):
    """A coincidence measurement requires at least 2 channels per group."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText("1")
    window.start_coincidences_measurement()

    assert mock_warn.called
    assert "at least 2 channels" in mock_warn.call_args[0][2].lower()
    assert window.coinc_worker is None


@pytest.mark.parametrize("repeated_input,expected_group", [
    ("1, 1", [1, 1]),
    ("1, 2, 1", [1, 2, 1]),
    ("2, 3, 2", [2, 3, 2]),
    ("1, 1, 1", [1, 1, 1]),
])
def test_validation_repeated_channels_in_group_allowed(qtbot, mocker, fake_workers, repeated_input, expected_group):
    """Repeated channels within a group are allowed and passed to the worker unchanged."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText(repeated_input)
    window.start_coincidences_measurement()

    assert not mock_warn.called
    assert coinc_kwargs(fake_workers)["coincidences"] == [expected_group]
    window.coinc_worker.start.assert_called_once()


def test_validation_channel_shared_across_groups_allowed(qtbot, mocker, fake_workers):
    """The same channel may appear in several groups (e.g. Swabian's [1, 2, 3] and [2, 3, 4])."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3, 4]
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText("1, 2, 3")
    window.coinc_btn_add.click()
    window.coinc_boxes[1].setText("2, 3, 4")
    window.start_coincidences_measurement()

    assert not mock_warn.called
    assert coinc_kwargs(fake_workers)["coincidences"] == [[1, 2, 3], [2, 3, 4]]
    window.coinc_worker.start.assert_called_once()


# =========================================================================
# 5. Channel Selection / Membership Corner Cases
# =========================================================================

def test_validation_channel_not_in_setup(qtbot, mocker):
    """Channel numbers not chosen in initial Channels Setup should trigger an error."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2] # User only chose 1 and 2
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    # Channel 3 is not chosen
    window.coinc_boxes[0].setText("1, 3")
    window.start_coincidences_measurement()

    assert mock_warn.called
    assert "Channel Not Selected" in mock_warn.call_args[0][1]
    assert "[3]" in mock_warn.call_args[0][2]
    assert "[1, 2]" in mock_warn.call_args[0][2]
    assert window.coinc_worker is None


def test_validation_all_channels_unselected(qtbot, mocker):
    """When none of the channels in the box were chosen in setup."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2]
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText("10, 11")
    window.start_coincidences_measurement()

    assert mock_warn.called
    assert "Channel Not Selected" in mock_warn.call_args[0][1]
    assert "10" in mock_warn.call_args[0][2] and "11" in mock_warn.call_args[0][2]
    assert window.coinc_worker is None


def test_validation_negative_channel_number(qtbot, mocker):
    """Negative channel numbers cannot be in selected channels."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2]
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText("-1, 2")
    window.start_coincidences_measurement()

    assert mock_warn.called
    assert "Channel Not Selected" in mock_warn.call_args[0][1]
    assert "-1" in mock_warn.call_args[0][2]
    assert window.coinc_worker is None


def test_validation_swabian_channel_ids(qtbot, fake_workers):
    """High Swabian channel IDs (e.g. 101, 102, 201) are handled correctly when chosen."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [101, 102, 201]

    window.coinc_boxes[0].setText("101, 201")
    window.start_coincidences_measurement()

    assert coinc_kwargs(fake_workers)["coincidences"] == [[101, 201]]
    window.coinc_worker.start.assert_called_once()


# =========================================================================
# 6. Multi-Box Addition, Removal & Group Validation Corner Cases
# =========================================================================

def test_multi_box_addition_and_removal_preserves_content(qtbot):
    """Adding and removing boxes preserves existing content and respects minimum of 1 box."""
    window = MainWindow()
    qtbot.addWidget(window)

    # Box 1 content
    window.coinc_boxes[0].setText("1, 2")

    # Add Box 2 and 3
    window.coinc_btn_add.click()
    window.coinc_boxes[1].setText("2, 3")
    window.coinc_btn_add.click()
    window.coinc_boxes[2].setText("3, 4")
    assert len(window.coinc_boxes) == 3

    # Remove Box 3
    window.coinc_btn_remove.click()
    assert len(window.coinc_boxes) == 2
    assert window.coinc_boxes[0].text() == "1, 2"
    assert window.coinc_boxes[1].text() == "2, 3"

    # Remove Box 2
    window.coinc_btn_remove.click()
    assert len(window.coinc_boxes) == 1
    assert window.coinc_boxes[0].text() == "1, 2"

    # Attempt to remove remaining box -> cannot remove below 1
    window.coinc_btn_remove.click()
    assert len(window.coinc_boxes) == 1
    assert window.coinc_boxes[0].text() == "1, 2"


def test_multi_box_second_box_empty_fails(qtbot, mocker):
    """When Box 1 is valid, but Box 2 is empty, validation should catch Box 2."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText("1, 2")
    window.coinc_btn_add.click()
    window.coinc_boxes[1].setText("") # Empty second box

    window.start_coincidences_measurement()
    assert mock_warn.called
    assert "group #2" in mock_warn.call_args[0][2]
    assert window.coinc_worker is None


def test_multi_box_second_box_unselected_channel_fails(qtbot, mocker):
    """When Box 1 has valid channels, but Box 2 uses a channel not chosen in setup."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]
    mock_warn = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")

    window.coinc_boxes[0].setText("1, 2")
    window.coinc_btn_add.click()
    window.coinc_boxes[1].setText("2, 99") # Channel 99 not chosen

    window.start_coincidences_measurement()
    assert mock_warn.called
    assert "group #2" in mock_warn.call_args[0][2]
    assert "[99]" in mock_warn.call_args[0][2]
    assert window.coinc_worker is None


def test_multi_box_overlapping_coincidence_groups_success(qtbot, fake_workers):
    """Multiple coincidence groups with overlapping channels (pairwise coincidences)."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]

    window.coinc_boxes[0].setText("1, 2")
    window.coinc_btn_add.click()
    window.coinc_boxes[1].setText("2, 3")
    window.coinc_btn_add.click()
    window.coinc_boxes[2].setText("1, 3")

    window.start_coincidences_measurement()

    assert coinc_kwargs(fake_workers)["coincidences"] == [[1, 2], [2, 3], [1, 3]]
    window.coinc_worker.start.assert_called_once()


# =========================================================================
# 7. Booking Error Handling Corner Case
# =========================================================================

def test_coincidences_booking_error_stops_measurement(qtbot, mocker, fake_workers):
    """If CoincidencesWorker reports a booking_error, UI shows critical error and stops."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2]
    window.coinc_boxes[0].setText("1, 2")
    mock_crit = mocker.patch("PyQt6.QtWidgets.QMessageBox.critical")
    fake_workers.booking_error = "Channels already booked by user_X"

    window.start_coincidences_measurement()

    assert mock_crit.called
    assert "Cannot Start Measurement" in mock_crit.call_args[0][1]
    assert "Channels already booked by user_X" in mock_crit.call_args[0][2]
    worker = fake_workers.created[-1]
    worker.start.assert_not_called()  # never start a measurement on unbooked channels
    assert window.coinc_worker is None


# =========================================================================
# 8. Multi-Stream Individual Data Streams & Plotting
# =========================================================================

def test_coincidences_multi_stream_curves_and_legend(qtbot):
    """When starting with N coincidence groups, N independent curves and buffers are created."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]

    # Setup 2 boxes: [1, 2] and [2, 3]
    window.coinc_boxes[0].setText("1, 2")
    window.add_coincidence_box()
    window.coinc_boxes[1].setText("2, 3")

    window.start_coincidences_measurement()

    assert window.coinc_worker is not None
    assert len(window.coinc_plot_curves) == 2
    assert len(window.coinc_ydata_streams) == 2
    assert window.coinc_plot_curve == window.coinc_plot_curves[0]
    assert window.coinc_groups == [[1, 2], [2, 3]]


def test_coincidences_multi_stream_plot_update(qtbot):
    """Multiplexed multi-stream updates distribute correctly to individual stream buffers."""
    import numpy as np
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]

    window.coinc_boxes[0].setText("1, 2")
    window.add_coincidence_box()
    window.coinc_boxes[1].setText("2, 3")

    window.start_coincidences_measurement()

    # Send 2D data: row 0 for stream 0, row 1 for stream 1
    mock_payload = np.array([[1542.0], [28.5]])
    window.update_coincidences_plot(mock_payload)

    assert len(window.coinc_ydata_streams[0]) == 1
    assert len(window.coinc_ydata_streams[1]) == 1
    assert window.coinc_ydata_streams[0][0] == 1542.0
    assert window.coinc_ydata_streams[1][0] == 28.5
    assert window.coinc_ydata[0] == 1542.0

    # Send a second frame
    mock_payload_2 = np.array([[1600.0], [35.0]])
    window.update_coincidences_plot(mock_payload_2)

    assert len(window.coinc_ydata_streams[0]) == 2
    assert len(window.coinc_ydata_streams[1]) == 2
    assert window.coinc_ydata_streams[0][-1] == 1600.0
    assert window.coinc_ydata_streams[1][-1] == 35.0


def test_coincidences_individual_stream_update(qtbot):
    """Direct per-stream update function properly routes to the target stream."""
    import numpy as np
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]

    window.coinc_boxes[0].setText("1, 2")
    window.add_coincidence_box()
    window.coinc_boxes[1].setText("2, 3")

    window.start_coincidences_measurement()

    window.update_coincidences_stream_plot(0, np.array([450.0]))
    window.update_coincidences_stream_plot(1, np.array([820.0]))

    assert window.coinc_ydata_streams[0][-1] == 450.0
    assert window.coinc_ydata_streams[1][-1] == 820.0


def test_coincidences_reset_clears_multi_streams(qtbot):
    """Resetting coincidences measurement resets all stream buffers, curves, and worker."""
    import numpy as np
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]

    window.coinc_boxes[0].setText("1, 2")
    window.add_coincidence_box()
    window.coinc_boxes[1].setText("2, 3")

    window.start_coincidences_measurement()
    window.update_coincidences_plot(np.array([[100.0], [200.0]]))

    assert len(window.coinc_plot_curves) == 2
    assert len(window.coinc_ydata_streams) == 2

    window.reset_coincidences_measurement()

    assert window.coinc_worker is None
    assert window.coinc_ydata_streams == []
    assert window.coinc_plot_curves == []




def test_coincidences_legend_checkboxes_toggle_curves(qtbot):
    """Each coincidence group gets a legend checkbox that shows / hides its curve."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.get_selected_channels = lambda: [1, 2, 3]

    window.coinc_boxes[0].setText("1, 2")
    window.add_coincidence_box()
    window.coinc_boxes[1].setText("2, 3")
    window.start_coincidences_measurement()

    checkboxes = [window.coinc_legend_layout.itemAt(i).widget()
                  for i in range(window.coinc_legend_layout.count())]
    assert [cb.text() for cb in checkboxes] == ["Coinc [1, 2]", "Coinc [2, 3]"]
    assert not window.coinc_legend_scroll.isHidden()

    checkboxes[1].setChecked(False)
    assert window.coinc_plot_curves[0].isVisible()
    assert not window.coinc_plot_curves[1].isVisible()
    checkboxes[1].setChecked(True)
    assert window.coinc_plot_curves[1].isVisible()

    window.reset_coincidences_measurement()
    assert window.coinc_legend_layout.count() == 0
    assert window.coinc_legend_scroll.isHidden()


def test_coincidences_zoom_toggle_switches_mouse_mode(qtbot):
    import pyqtgraph as pg
    window = MainWindow()
    qtbot.addWidget(window)
    vb = window.coinc_plot_widget.getViewBox()

    window.coinc_btn_zoom.click()
    assert vb.state['mouseMode'] == pg.ViewBox.RectMode
    window.coinc_btn_zoom.click()
    assert vb.state['mouseMode'] == pg.ViewBox.PanMode
