```
                                                                                                                               ______   
   _______     _______     ____________  _____    _____           __     __      ________    ________         ____       _____|\     \  
  /      /|   |\      \   /            \|\    \   \    \         /  \   /  \    /        \  /        \    ____\_  \__   /     / |     | 
 /      / |   | \      \ |\___/\  \\___/|\\    \   |    |       /   /| |\   \  |\         \/         /|  /     /     \ |      |/     /| 
|      /  |___|  \      | \|____\  \___|/ \\    \  |    |      /   //   \\   \ | \            /\____/ | /     /\      ||      |\____/ | 
|      |  |   |  |      |       |  |       \|    \ |    |     /    \_____/    \|  \______/\   \     | ||     |  |     ||\     \    | /  
|       \ \   / /       |  __  /   / __     |     \|    |    /    /\_____/\    \\ |      | \   \____|/ |     |  |     || \     \___|/   
|      |\\/   \//|      | /  \/   /_/  |   /     /\      \  /    //\_____/\\    \\|______|  \   \      |     | /     /||  \     \       
|\_____\|\_____/|/_____/||____________/|  /_____/ /______/|/____/ |       | \____\        \  \___\     |\     \_____/ | \  \_____\      
| |     | |   | |     | ||           | / |      | |     | ||    | |       | |    |         \ |   |     | \_____\   | /   \ |     |      
 \|_____|\|___|/|_____|/ |___________|/  |______|/|_____|/ |____|/         \|____|          \|___|      \ |    |___|/     \|_____|      
                                                                                                         \|____|                        
```

A terminal-based task manager for Windows, inspired by `htop`.

## Features

### System Monitor
- **Hardware Info**: CPU model and Disk model displayed at top
- **CPU**: Per-core usage bars with color coding + total average
- **GPU**: GPU name and utilization (heuristic detection on discrete or integrated)
- **Memory**: RAM usage with used/total
- **Pagefile**: Windows pagefile (swap) usage
- **Disk**: Usage bar + SMART health status
- **Network**: Live upload/download speeds
- **Disk I/O**: Real-time read/write speeds
- **Secrets**: Maybe if you read the source code you can find something interesting

### Process Manager
- Scrollable process list (Arrow Keys, PgUp/PgDn, Home/End)
- Accurate(ish) per-process CPU% (calculated from cpu_times)
- Sort by PID, Name, CPU%, or Memory%
- Filter processes by name
- Color-coded high CPU usage

### Commands
| Command | Description |
|---------|-------------|
| `kill <pid\|name>` | Terminate process(es) |
| `suspend <pid\|name>` | Pause process(es) |
| `resume <pid\|name>` | Resume paused process(es) |
| `info <pid>` | Show detailed process info |
| `sort <column>` | Sort by `pid`, `cpu`, `mem`, or `name` |
| `filter <text>` | Filter processes by name |
| `speed <rate>` | Set refresh: `slow`, `medium`, `fast`, `superfast` |
| `export [file]` | Export process list to file |
| `quit` | Exit the application |
| `showdrives` | Toggle display of all drives |

### Controls
| Key | Action |
|-----|--------|
| ↑/↓ | Scroll process list |
| PgUp/PgDn | Scroll by 10 |
| Home/End | Jump to top/bottom |
| Delete/Backspace | Delete character |
| Esc | Clear input |
| Enter | Execute command |

## Installation (Setup)

Simply go to releases and download the latest installer or use the ps1 files attached, choose your options (ps1 does not support this) and you're ready to use winhtop in the terminal. Uninstalling should be easy aswell.

## Requirements

- Windows 10/11
- Python 3.13+
- `psutil`

## Installation (DIY)

This installs WinHtop to the same location used by the packaged installer/script, but transparency is important

```bash
git clone https://github.com/yourusername/winhtop.git
cd winhtop
pip install --user -r requirements.txt
```

Create the install directory:

```bash
mkdir "%LOCALAPPDATA%\Programs\WinHtop"
```

Copy the program files:

```bash
copy task_manager.py "%LOCALAPPDATA%\Programs\WinHtop\winhtop.py"
xcopy modules "%LOCALAPPDATA%\Programs\WinHtop\modules" /E /I /Y
```

Create a simple launcher so you can run it as winhtop:

```bash
echo @echo off > "%LOCALAPPDATA%\Programs\WinHtop\winhtop.cmd"
echo python "%%LOCALAPPDATA%%\Programs\WinHtop\winhtop.py" %%* >> "%LOCALAPPDATA%\Programs\WinHtop\winhtop.cmd"
```

Add the install directory to your User PATH:

```bash
setx PATH "%PATH%;%LOCALAPPDATA%\Programs\WinHtop"
```

Open a new terminal, then run:
```bash
winhtop
```

Uninstalling is as easy as:
Deleting the program folder
```bash
rmdir /S /Q "%LOCALAPPDATA%\Programs\WinHtop"
```
And removing the PATH entry, optional but tidy

```bash
setx PATH "%PATH:;%LOCALAPPDATA%\Programs\WinHtop=%"
```

## Disclaimer

This program (or the installer attached) is unable to:
- Change registry values (apart from uninstall marking)
- Sniff the network
- Or other malicious activities

It is not my responsibility if you also run `kill csrss.exe`, most important system processes are blacklisted/protected from this command though, killing the wrong process can cause system instability or you to be logged out.
This program is provided as-is, without any warranty. Use at your own risk.

Also it may be a bit slow on some lower end systems, but it should work fine for when you need it.