# MaaS-GUI User Guide

Welcome to the Measurement as a Service (MaaS) Graphical User Interface! This application allows you to remotely control time-tagging and photon-counting hardware, run real-time measurements, and visualize the data.

## Getting Started

### 1. Account & Connection
When you launch the application, you'll start on the **Account** tab.
- Enter your **Username** and **Password**.
- Click **Login** to authenticate with the backend server. The application receives a JWT token and decodes it to determine your assigned role.
- **Account Password Update**: You can change your password anytime under the **Account** tab by providing your current password and entering a new password.
- **Admin Users ("User Management" tab)**: If the decoded token identifies you as an **Admin**, a dedicated **User Management** tab is unlocked. This unified panel contains a dropdown allowing the administrator to switch between three actions:
  - **Add User**: Register new user accounts in MaaS (selecting either **Operator** or **Viewer** role). Initial password defaults to the username.
  - **Delete User**: Permanently remove user accounts from the MaaS platform with confirmation safeguards (self-deletion of the active admin account is prohibited).
  - **Change User Password**: Directly set a new password for any existing user account on the platform without requiring their current password.
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
The Coincidences tab measures simultaneous events (coincidences) across channels within a specific coincidence window.

- Set the **Coincidence Window (ps)** to define how close two events must be to be considered simultaneous (default: 1000 ps = 1 ns).
- Enter comma-separated channel numbers in each box (e.g. `"1, 2"` or `"1, 2, 3"`).
- By default, 1 box is open. Use the **`+`** icon to add additional coincidence group boxes for concurrent multi-group measurements, and **`-`** to remove them.
- **Validation**: When starting a measurement, the application validates that input formats are correct and that all entered channels correspond to channels chosen in the initial Channels Setup tab.
- **Individual Data Streams & Plotting**: Each coincidence channel group has an individual data stream with its own color-coded plot curve and legend entry, visualizing simultaneous events across all specified groups concurrently.
- **Time step**: Choose how often a new point is plotted (10 ms to 1 s, default 40 ms). Changing it while a measurement is running restarts the measurement. The x-axis shows the elapsed measurement time in seconds.
- **Points**: How many of the most recent points are kept on the plot (default 100).
- **What is plotted**: Each point is the average coincidence rate in counts/s since the measurement started (the backend uses the Time Tagger's `Countrate`), so curves settle over time rather than showing per-step counts.
- **Zoom & legend**: Use the **⌕** button to drag a box to zoom, **⤢** to return to auto range, and the legend checkboxes to show or hide individual groups.

---

## General UI Controls

On every measurement tab, you'll find a standard set of tools to interact with your data:

- **Play / Pause**: Start or temporarily pause the measurement.
- **Stop**: Halts the background measurement worker entirely, freeing up resources and unlocking your tabs, while perfectly preserving the visible data.
- **Reset**: Completely clears the plot and resets the measurement state.
- **Zoom / Auto-range**: Toggle manual zooming or force the plot to automatically scale to fit all incoming data.
- **Export**: Save the currently plotted data to a CSV file for offline analysis.
