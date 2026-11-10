# MaaS-GUI: Quick Start for Time Tagger Users

MaaS (Measurement as a Service) puts the lab's Swabian Time Tagger on a shared server. MaaS-GUI is the desktop app you use it: you book channels, run Counter, Histogram and Coincidence measurements, and save the data, all from your own PC.

## Install

1. Download `MaaS-GUI.exe` from the latest release on [GitHub Releases](https://github.com/ghm213-ku/MaaS-GUI/releases).
2. Launch the .exe file, ignore the warnings while launched.
3. Your PC must be on the lab network (or VPN) that can reach the MaaS server.

To try the app without hardware, start it as `MaaS-GUI.exe -testing`: login is skipped and all plots show some random data.

## First-time setup

1. **Get an account.** Ask an admin to create one with your chosen username. Your initial password is the same as your username.
2. **Check the server.** On the **Account** tab the MaaS server address is pre-filled.
3. **Log in** with your username and password.
4. **Change your password** right away, under *Change Password* on the same tab.

The status panel at the top of **Channels Setup** shows whether MaaS is live; **Refresh** re-checks it.

## Channels

The Time Tagger is shared, so you must book a channel before you can measure on it or change its settings. Measurements use only blue channels. Everything happens on the **Channels Setup** tab, where each channel is a circle.

| Circle | Meaning |
| --- | --- |
| White | Free |
| Blue | Selected: booked by you and used in measurements, or picked for booking |
| Green | Booked by you but left out of measurements (left-click to include again) |
| Grey | Booked by someone else; hover to see who |

- **Book**: left-click the channels you want, then click **Book**.
- **Trigger level and delay**: right-click one of your booked channels and enter trigger (V) and delay (ps). The values shown under the channel are read back from the hardware. Defaults are 0.5 V and 0 ps.
- **Release**: select your booked channels and click **Release** when you are done. Released channels go back to 0.5 V / 0 ps.

**Please release channels at the end of every session; nobody else can use them until you do.**

## Measurements

There are three measurement tabs. They behave like the Time Tagger measurements of the same name, and all times are in ps (`1e9` = 1 ms). Only channels you have booked can be used.

**Controls on every tab**

| Button | Does |
| --- | --- |
| Play / Pause | Start, pause, resume |
| Stop | Ends the measurement but keeps the plot |
| Reset | Ends it and clears the plot |
| ⌕ | Zoom mode: drag a box on the plot |
| ⤢ | Auto-range: fit the data to the screen again |
| Save (Export) | Saves the plotted data as a NumPy `.npy` file |

While a measurement runs you cannot switch tabs. Stop or pause it first.

**Counter.** Counts per bin on each blue channel. Set *Bin width* (default 1 ms) and *Bins* (default 1000), then choose a mode:

- *Free Running*: runs until stopped. Once the buffer of *Bins* bins has filled, each bin keeps adding up counts frame by frame.
- *Single*: records exactly Bins × Bin width (for example 1000 × 1 ms = 1 s), then stops by itself.
- *Repeating*: sets Bin width to 1 s and locks Bins to 1. Each bin's total becomes a new point on a scrolling chart.

**Histograms.** Pick a mode (*Start-Stop*, *Histogram* or *Correlation*), a start channel and a click channel, a bin width and a number of bins. Press Enter in a field to restart with the new value. The bold **+** at the top right opens a second, independent Histograms tab.

- **Filter**: click **Filter** to add a yellow time window. Drag its edges, or right-click the button to type exact bounds such as `250ns` or `1.5us`.
- **Second filter**: click the **+** next to Filter for a cyan window.
- The lower plot shows counts inside each filter over time, and has its own save button.

**Coincidences.** Set the *Coincidence window* (default 1000 ps), then type a channel group such as `1, 2` or `1, 2, 3` (at least two channels). Use **+** / **−** to add or remove groups; each group gets its own trace, which you can hide with its legend checkbox. *Bin width* and *Bins* set the time axis, which spans Bins × Bin width (default 1000 × 1 ms = 1 s).

## For admins: managing accounts

Admins see an extra **User Management** tab with a dropdown of three actions.

- **Add User**: enter a username and pick a role: *Operator* (runs measurements), *Viewer*, or *Admin*. The initial password is the username, so tell the new user to change it.
- **Delete User**: removes an account after a confirmation. You cannot delete your own account.
- **Change User Password**: sets a new password for any user without needing the old one. Use this when someone forgets theirs.

## Common errors and fixes

| Message or symptom | What to do |
| --- | --- |
| *Connection Failed* / *Could not connect* | Check you are on the lab network or VPN and the server address is right, then **Test Connection** on the Account tab |
| *Backend Unavailable* or status panel not live | The server is up but not healthy. Wait a minute and **Refresh**; if it persists, tell the admin |
| *Authentication Failed* | Wrong username or password. An admin can reset it |
| *Channel Not Booked* | Book the channel on Channels Setup first. Measurements never book channels for you |
| Grey channel you need | Someone else has it; hover to see who, and ask them to release it |
| *Set Parameters Pending / Failed* | The trigger or delay was not applied. Right-click the channel and try again; the shown values are what the hardware really has |
| *Invalid Format* (Coincidences) | Use comma-separated whole numbers, at least two per group, all booked by you |
| Cannot switch tabs | A measurement is running; Stop or Pause it |
| App closes or behaves oddly | Send the admin the log file `%LOCALAPPDATA%\MaaS-GUI\maas_gui.log` and the version from the window title |

## Further reading

- [MaaS-GUI User Guide](USER_GUIDE.md): the full reference, covering every control, field default, counter mode, filter, saved file format and error message.
- [Time Tagger user manual](https://www.swabianinstruments.com/static/documentation/TimeTagger/): Swabian's documentation. The measurement pages matching the GUI tabs are [Counter](https://www.swabianinstruments.com/static/documentation/TimeTagger/api/measurements/event_counting.html#counter), [StartStop, Histogram and Correlation](https://www.swabianinstruments.com/static/documentation/TimeTagger/api/measurements/time_histograms.html), and [Coincidences](https://www.swabianinstruments.com/static/documentation/TimeTagger/api/VirtualChannels.html#coincidences).
