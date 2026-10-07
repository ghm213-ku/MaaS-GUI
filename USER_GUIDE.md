# MaaS-GUI User Guide

Welcome to the Measurement as a Service (MaaS) Graphical User Interface! This application allows you to remotely control time-tagging and photon-counting hardware, run real-time measurements, and visualize the data.

## Getting Started

### 1. Account & Connection
When you launch the application, you'll start on the **Account** tab.
- Enter your **Username** and **Password**.
- Click **Connect** to authenticate with the backend server.
- *(Note: If you are running the app in testing mode, authentication will be bypassed.)*

### 2. Channels Setup
After connecting, navigate to the **Channels Setup** tab.
- Here, you will see a list of available hardware channels.
- Select the checkboxes for the channels you wish to reserve for your experiment.
- Click **Apply** to book the channels. Once booked, they become available in the measurement tabs.

---

## Measurements

The application features three main types of measurements: **Counter**, **Histograms**, and **Coincidences**.

> [!IMPORTANT]  
> **Tab Locking**: To ensure stable data collection and prevent hardware conflicts, you cannot switch to another tab while a measurement is actively running. You must **Pause**, **Stop**, or wait for a single-shot measurement to finish before switching tabs.

### Counter Tab
The Counter tab displays the raw count rates (events per second) for all your booked channels over time.

- **Modes**:
  - **Free Running**: Continuously collects and plots data indefinitely.
  - **Single**: Collects a fixed number of data points (defined by *N values*), then stops automatically.
  - **Repeating**: Collects *N values*, clears the plot, and starts over repeatedly.
- **Bin Width (ps)**: The time duration of each data point.
- **N values**: How many points to collect (applicable in Single and Repeating modes).
- **Controls**: Play/Pause, Stop (halts measurement but keeps data on screen), and Reset (halts measurement and clears the screen).

### Histograms Tab
The Histograms tab allows you to measure the time differences between events on two specific channels.

- **Start Channel & Click Channel**: Choose which channel triggers the timer and which channel stops it.
- **Dual Tabs**: You can click the bold **`+`** button in the top right corner of the application to open a **Histograms 2** tab. This allows you to set up and run two entirely independent histogram configurations without losing your setup.
- **Filters**:
  - Click the **Filter** button to enable a highlighted region (Yellow).
  - Click the **`+`** button next to the Filter button to add a secondary filter (Cyan).
  - **Custom Values**: Right-click the filter button to manually type exact time boundaries (e.g., "250ns" or "1.5us").
  - The bottom plot tracks how many counts fall within your filter(s) over time.

### Coincidences Tab
The Coincidences tab measures simultaneous events (coincidences) across pairs of channels within a specific coincidence window.

- Set the **Coincidence Window (ps)** to define how close two events must be to be considered simultaneous.
- The plot visualizes the coincidence rates between all combinations of your booked channels.

---

## General UI Controls

On every measurement tab, you'll find a standard set of tools to interact with your data:

- **Play / Pause**: Start or temporarily pause the measurement.
- **Stop**: Halts the background measurement worker entirely, freeing up resources and unlocking your tabs, while perfectly preserving the visible data.
- **Reset**: Completely clears the plot and resets the measurement state.
- **Zoom / Auto-range**: Toggle manual zooming or force the plot to automatically scale to fit all incoming data.
- **Export**: Save the currently plotted data to a CSV file for offline analysis.
