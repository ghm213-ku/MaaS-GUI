# MaaS-GUI User Guide

MaaS (Measurement as a Service) runs the lab's Swabian Time Tagger on a shared server. MaaS-GUI is the desktop app for it: you log in, book channels, run Counter, Histogram and Coincidence measurements, and save the data from your own PC. The measurements behave like the Time Tagger API classes of the same name, and all times you type are in picoseconds (`1e9` ps = 1 ms) unless stated otherwise.

**Contents**

1. [Installing and running](#1-installing-and-running)
2. [Logging in](#2-logging-in)
3. [The main window](#3-the-main-window)
4. [Channels Setup](#4-channels-setup)
5. [Controls shared by all measurement tabs](#5-controls-shared-by-all-measurement-tabs)
6. [Counter](#6-counter)
7. [Histograms](#7-histograms)
8. [Coincidences](#8-coincidences)
9. [Saved data formats](#9-saved-data-formats)
10. [Account tab](#10-account-tab)
11. [User Management (admins)](#11-user-management-admins)
12. [Common errors and fixes](#12-common-errors-and-fixes)
13. [Further reading](#13-further-reading)

---

## 1. Installing and running

- **Standalone (recommended)**: download `MaaS-GUI.exe` from the latest [GitHub release](https://github.com/ghm213-ku/MaaS-GUI/releases) and double-click it. It is a single file: no installer and no Python. The first launch takes a few seconds while it unpacks.
- **From source**: `pip install -r requirements.txt`, then `python main.py`.
- **Testing mode**: start with `-testing` (`MaaS-GUI.exe -testing` or `python main.py -testing`; for the exe, add it to a shortcut's *Target* field). No server is contacted, any username and password are accepted, and every plot shows generated data. Log in as `admin` to see the admin tab. Use this to learn the app.
- **Network**: your PC must be able to reach the MaaS server (lab network or VPN).
- **Version**: shown in the window title and in the exe's *Properties → Details*. Quote it when you report a problem.
- **Log file**: `%LOCALAPPDATA%\MaaS-GUI\maas_gui.log`. All errors, including crashes, are written there.
- **Building the exe** (developers): run `build.bat`; it produces `dist\MaaS-GUI.exe`. See [RELEASING.md](RELEASING.md) for versioning and releases.

## 2. Logging in

You need an account first: ask a MaaS admin to create one. **Your initial password is your username**; change it after your first login (see [Account tab](#10-account-tab)).

The login screen has three fields:

- **Username** and **Password**.
- **MaaS IP**: the server address, pre-filled with the lab default (or the `MAAS_IP` / `MAAS_HOST` environment variable if set). It accepts `host`, `host:port` (default port 8000) or a full `http(s)://` URL.

Pressing Enter moves from field to field; Enter in the IP field logs in. Your role (Admin, Operator or Viewer) comes from the server after login.

## 3. The main window

Tabs, left to right: **Channels Setup**, **Counter**, **Histograms**, **Coincidences**, **Account**, and **User Management** for admins. The bold **+** at the top right adds a **Histograms 2** tab (one extra at most).

**Tab locking**: while a measurement is running, the other tabs are disabled. Stop it, pause it, or let a Single run finish before switching.

Warnings about the live data stream (for example a stalled histogram) appear for 15 s in the status bar at the bottom of the window, without interrupting you.

## 4. Channels Setup

### MaaS status panel

The card at the top shows whether the server is usable:

| State | Meaning |
| --- | --- |
| Live (green) | Server reachable and healthy |
| Degraded (amber) | Reachable, but reports a non-healthy status |
| Error (red) | Server answered with an HTTP error |
| Offline (red) | Server cannot be reached |
| Checking… / Testing mode (grey) | Check in progress / running with `-testing` |

It re-checks every 15 s; **Refresh** checks now. Hover over the state for the reason. The line below shows the server address, latency, health status, your username and role, and when your login session expires (marked *expired* once it has).

### The channel grid

Channels 1–18 are shown as circles:

| Circle | Meaning | Click behaviour |
| --- | --- | --- |
| White | Free | Left-click to select |
| Blue | Selected: booked by you and used in measurements, or chosen for booking | Left-click to deselect |
| Green | Booked by you but deselected (left out of measurements) | Left-click to select again |
| Grey | Booked by someone else; hover to see who | Not clickable |

Measurements only use **blue** channels. Counter plots every blue channel, the Histograms dropdowns list them, and Coincidence groups may only contain them.

### Booking and releasing

- **Book**: select free channels (blue) and click **Book**. They stay booked to you, and stay blue, until you release them. Closing the app does **not** release them.
- **Release**: select your booked channels (blue) and click **Release**. Only selected channels that are yours are released. Released channels are reset on the hardware to 0.5 V trigger and 0 ps delay.
- Release your channels at the end of each session; no one else can use them until you do.

### Trigger level and input delay

Right-click one of your booked channels to open its settings:

- **Trigger (V)**: threshold voltage (decimal comma or point both work).
- **Delay (ps)**: input delay, a whole number.

Enter moves to the next field and then applies; **Save** applies too. The values are sent to the Time Tagger, and the two numbers under the circle are re-read from the hardware, so they always show what the device really has. Defaults are 0.5 V and 0 ps. These are hardware settings: change them only on channels you have booked.

## 5. Controls shared by all measurement tabs

| Control | Action |
| --- | --- |
| ▶ / ⏸ Play / Pause | Start; pause and resume without losing data |
| ■ Stop | End the measurement and keep the plot (unlocks the tabs) |
| ⟳ Reset | End the measurement and clear the plot |
| ⌕ Zoom | Toggle zoom mode: drag a box to zoom in. When it is off, drag to pan |
| ⤢ Auto-range | Fit the data to the screen again (stays on until you zoom or pan) |
| 💾 Save | Save the plotted data as a `.npy` file (Counter and Histograms; enabled when paused or stopped) |

Other plot features:

- **Hover cursor**: a dashed vertical line follows the mouse and shows the nearest bin's x value and the y value of each visible curve.
- **Legend checkboxes** (Counter, Coincidences): show or hide individual curves.
- **Mouse wheel**: zooms the plot.
- While a measurement runs, its settings fields are locked. Where noted below, pressing **Enter** in a field restarts the measurement with the new value.

## 6. Counter

Count rates on all blue channels (Time Tagger `Counter`). The plot refreshes 25 times per second.

| Field | Meaning | Default |
| --- | --- | --- |
| Mode | Free Running, Single or Repeating | Free Running |
| Bin_width (ps) | Duration of one bin | `1e9` (1 ms) |
| Bins | Number of bins in the buffer (*n_values*) | 1000 |

**Modes**

- **Free Running**: runs until stopped. The Counter keeps a rolling buffer of *Bins* bins. While the buffer fills, the live snapshot is shown and the title reads *filling buffer… x%*. After that, each new frame is added bin by bin, and the title shows *accumulated over N frames* (y-axis: accumulated counts per bin).
- **Single**: acquires exactly *Bins* × *Bin_width* of data (for example 1000 × 1 ms = 1 s), then stops by itself. Each bin shows counts per bin.
- **Repeating**: sets Bin_width to `1e12` (1 s) and Bins to 1 (locked). Each bin's total is appended as a new point, so you get a slow strip chart of counts per bin over *Time Steps*. The last 200 points are kept and the last 60 are shown.

The x-axis is the bin index. Enter in Bin_width or Bins starts a new run if the measurement is stopped or in Single mode.

## 7. Histograms

Time differences between a **Start** channel and a **Click** channel.

| Field | Meaning | Default |
| --- | --- | --- |
| Mode | Start-Stop, Histogram or Correlation | Start-Stop |
| Start Ch / Click Ch | Chosen from your blue channels | First two blue channels |
| Bin_width (ps) | Histogram bin width | 1000 |
| Bins | Number of bins (not used in Start-Stop) | 1000 |

**Modes** (same as the Time Tagger classes):

- **Start-Stop** (`StartStop`): each click is paired with the most recent start. The number of bins is not fixed, so *Bins* is disabled.
- **Histogram** (`Histogram`): click times after each start, over *Bins* × *Bin_width*.
- **Correlation** (`Correlation`): a two-sided histogram centred on zero. Delay = t(click) − t(start).

The x-axis is time in seconds with SI prefixes (ns, µs, …). Press Enter in Bin_width or Bins to restart with the new value. Very large bin counts can stall the live stream; the status bar then suggests using fewer bins.

### Filters

Filters sum the counts inside a time window and track that sum over time. The **Filter** button appears once a mode is chosen.

1. Click **Filter**. A yellow window (F1) appears around the middle of the histogram, about 20 % of the range wide. Drag the window to move it, or drag its edges to resize it.
2. Click the **+** next to Filter to add a second, cyan window (F2). The button turns into **−**, which removes F2 again.
3. **Exact bounds**: right-click **Filter** while it is on. Type a min and max for each window with units `ps`, `ns`, `us`, `ms` or `s` (for example `250ns`, `1.5us`; no unit means seconds), then press Enter.
4. A **Sum in Filter** plot opens below the histogram. Its x-axis is the time in seconds since the filter was switched on. Its y-axis is the total histogram counts inside each window, recalculated on every update (F1 yellow, F2 cyan). The last 10,000 points are kept.
5. The filter plot has its own ⌕ zoom, ⤢ auto-range and 💾 save buttons. It scrolls to follow the newest point; any manual zoom or pan stops following until you press ⤢.

Switching the filter off and on, or resetting the histogram, restarts the filter trace.

### Histograms 2

The **+** at the top right of the window opens a second Histograms tab with identical, fully independent settings, filters and saving. Each tab locks the others while it runs.

## 8. Coincidences

Coincidence rates for groups of channels: Time Tagger `Coincidences` virtual channels, fed into a `Counter`.

| Field | Meaning | Default |
| --- | --- | --- |
| Coincidence Window (ps) | Maximum spread of events counted as coincident; positive integer | 1000 (1 ns) |
| Bin width (ps) | Duration of one counter bin; positive whole number | `1e9` (1 ms) |
| Bins | Bins in the rolling window; the plot spans Bins × Bin width | 1000 (→ 1 s) |
| Channels | One box per group, comma-separated, such as `1, 2` or `1, 2, 3` | One box |

- **+** adds a group box and **−** removes the last one. All groups run at the same time, each with its own coloured curve and legend checkbox.
- Every group needs **at least two** channels, written as integers separated by single commas, and all of them must be blue (booked and selected) in Channels Setup. Otherwise the app explains what is wrong and does not start.
- The plot shows coincidences per bin. The x-axis is time in seconds, with 0 at the newest bin and older bins to the left. It refreshes 25 times per second.
- Press Enter in Bin width or Bins while running to restart with the new values.
- The hover cursor shows each group's value at the nearest bin.
- This tab has no save button.

## 9. Saved data formats

All saves are NumPy `.npy` files (the extension is added if you leave it out). Load them with `numpy.load("file.npy")`; each is a 2-D array with one row per point.

| Saved from | Columns |
| --- | --- |
| Counter | bin index, then one column per channel (in channel order) |
| Histograms / Histograms 2 | time (s), counts per bin |
| Sum in Filter plot | elapsed time (s), sum in F1, sum in F2 (if F2 is on) |

## 10. Account tab

- **MaaS Server Connection**: enter a server IP, hostname or URL. **Apply Server IP** switches to it. **Test Connection** checks it and reports the server's health.
- **Account Password Update**: enter your current password and the new password twice, then click **Change Password**.

## 11. User Management (admins)

Only visible to users with the Admin role. Pick an operation from **Select Operation**:

- **Add User**: username and user type (*Operator*, *Viewer* or *Admin*). The initial password is the username.
- **Delete User**: permanently removes an account after confirmation. You cannot delete your own account.
- **Change User Password**: sets a new password (entered twice) for any user, without their current one. Use it when someone forgets their password.

The result of each action is shown below the form and in a pop-up.

## 12. Common errors and fixes

| Message or symptom | Cause | Fix |
| --- | --- | --- |
| *Authentication Failed: Invalid credentials* | Wrong username or password | Retype it; new accounts use the username as password. An admin can reset it |
| *Connection Error* at login / *Connection Failed* | Server unreachable | Check the network or VPN and the MaaS IP; use **Test Connection** |
| Status panel *Offline* or *Error* | Server down or unreachable | Press **Refresh**; if it persists, contact the MaaS admin |
| Status panel *Degraded* / *Backend Unavailable* on Start | Server is up but not healthy | Wait a minute and retry; tell the admin if it continues |
| *Session expires … (expired)* in the status panel, requests start failing | Login token expired | Close the app and log in again |
| *No Channels* | No blue channels selected | Select or book channels on Channels Setup |
| *Channel Not Booked* | You tried to change, or measure on, a channel you have not booked | Book it first; measurements never book channels for you |
| *Cannot Start Measurement* (channels booked by others) | A channel you chose belongs to someone else | Pick another channel or ask the owner (hover the grey circle) to release it |
| *Booking Failed* | Channel was taken in the meantime | Channels Setup refreshes after the attempt; pick free channels |
| *Set Parameters Pending* | The server queued the trigger/delay but has not applied it within 10 s | Wait; the numbers under the channel update once it is applied. Retry if they don't |
| *Set Parameters Failed* | The Time Tagger rejected the value | Check the value is within the device's range; the shown numbers are the real ones |
| *Invalid Input* (Bin width, Bins, window) | Not a valid number | Bin widths and windows in whole ps (`1e9` is fine), Bins a positive integer |
| *Invalid Format* / *Invalid Selection* / *Channel Not Selected* (Coincidences) | Bad group text | Use `1, 2, 3` style, two or more channels, all blue in Channels Setup |
| Status bar: *No histogram data from MaaS for N s* | Histogram too large to stream | Reduce Bins |
| Status bar: *MaaS closed the histogram data stream* | Server ended the stream | Press Stop, then start again |
| Cannot switch tabs | A measurement is running | Stop or pause it |
| Save button greyed out | Measurement is running | Pause or stop first |
| Grey channels you expected to be yours | Booked under another username | Check the user shown in the status panel |
| App freezes, closes, or anything else odd | Bug | Send `%LOCALAPPDATA%\MaaS-GUI\maas_gui.log` and the version number from the window title to the maintainers |

## 13. Further reading

- [Time Tagger user manual](https://www.swabianinstruments.com/static/documentation/TimeTagger/): Swabian's full documentation. The relevant sections:
  - [Getting started](https://www.swabianinstruments.com/static/documentation/TimeTagger/gettingStarted/index.html)
  - [Counter](https://www.swabianinstruments.com/static/documentation/TimeTagger/api/measurements/event_counting.html#counter)
  - [StartStop](https://www.swabianinstruments.com/static/documentation/TimeTagger/api/measurements/time_histograms.html#startstop), [Histogram](https://www.swabianinstruments.com/static/documentation/TimeTagger/api/measurements/time_histograms.html#histogram), [Correlation](https://www.swabianinstruments.com/static/documentation/TimeTagger/api/measurements/time_histograms.html#correlation)
  - [Coincidences](https://www.swabianinstruments.com/static/documentation/TimeTagger/api/VirtualChannels.html#coincidences)
- [RELEASING.md](RELEASING.md): how versions and releases are made (developers).
