"""Input detection module"""
import msvcrt
import psutil
from .state import state
from .config import *
from .processes import get_process_tree_info
try:
    from .audio_vis import AudioVisualizer, AUDIO_AVAILABLE
except ImportError:
    AUDIO_AVAILABLE = False
    AudioVisualizer = None

def execute_pending_action():
    """Execute the pending confirmed action."""
    if not state.pending_confirmation:
        return
    
    action, targets, original_arg = state.pending_confirmation
    state.pending_confirmation = None
    
    protected = ["system", "registry", "memcompression", "secure system", "csrss.exe", "smss.exe", "lsass.exe", "wininit.exe", "services.exe", "winlogon.exe", "svchost.exe", "dwm.exe", "fontdrvhost.exe", "logonui.exe"]
    
    success, errors = 0, 0
    
    for p in targets:
        try:
            pname = p.name().lower()
            
            if action == "kill" and pname in protected:
                state.status_message = f"BLOCKED: {p.name()} is critical to Windows"
                errors += 1
                continue
            
            if action == "kill":
                p.terminate()
                success += 1
            elif action == "suspend":
                p.suspend()
                success += 1
            elif action == "resume":
                p.resume()
                success += 1
        except psutil.AccessDenied:
            state.status_message = f"Access denied (run as Admin)"
            errors += 1
        except psutil.NoSuchProcess:
            state.status_message = f"Process no longer exists"
            errors += 1
        except Exception:
            errors += 1
    
    action_names = {"kill": "Killed", "suspend": "Suspended", "resume": "Resumed"}
    state.status_message = f"{action_names[action]} {success}, Errors: {errors}"

def handle_party_command():
    """Toggle party mode (audio visualizer easter egg)."""
    if not AUDIO_AVAILABLE:
        state.status_message = "Some people in this party are missing..."
        return
    
    if state.party_mode:
        state.party_mode = False
        if state.party_visualizer:
            state.party_visualizer.stop()
            state.party_visualizer = None
        
        if state.party_prev_refresh_rate:
            state.current_refresh_rate = state.party_prev_refresh_rate
            state.party_prev_refresh_rate = None
        
        state.status_message = "Party's over... back to work!"
    else:
        try:
            num_cores = len(state.sys_stats.get("cpu_per_core", [])) or psutil.cpu_count() or 8
            state.party_visualizer = AudioVisualizer(num_cpu_cores=num_cores)
            
            if state.party_visualizer.start():
                state.party_mode = True
                state.party_prev_refresh_rate = state.current_refresh_rate
                state.current_refresh_rate = "party"
                state.status_message = "🎉 Party mode activated! Type 'party' again to stop."
            else:
                state.party_visualizer = None
                state.status_message = "Some people in this party are missing..."
        except Exception:
            state.party_visualizer = None
            state.status_message = "Some people in this party are missing..."

def execute_command(cmd_str):
    """Parse and execute a command."""
    parts = cmd_str.strip().split(maxsplit=1)
    if not parts:
        return
    
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    
    if cmd in ["quit", "exit", "q"]:
        state.app_running = False
        return
    
    if cmd == "party":
        handle_party_command()
        return
    
    if cmd == "help":
        state.status_message = "kill|suspend|resume|info, sort, filter, speed, showdrives, export, quit"
        return
    
    if cmd == "showdrives":
        state.show_all_drives = not state.show_all_drives
        if state.show_all_drives:
            drive_count = len(state.sys_stats.get('all_disks', []))
            state.status_message = f"Showing all drives ({drive_count} found)"
        else:
            state.status_message = "Showing only C: drive"
        return
    
    if cmd == "speed":
        speeds = list(REFRESH_RATES.keys())
        if arg.lower() in REFRESH_RATES:
            state.current_refresh_rate = arg.lower()
            state.status_message = f"Refresh rate: {state.current_refresh_rate} ({REFRESH_RATES[state.current_refresh_rate]}s)"
        else:
            state.status_message = f"Usage: speed [{'/'.join(speeds)}]"
        return
    
    if cmd == "sort":
        col_map = {"pid": "pid", "cpu": "cpu_percent", "mem": "memory_percent", "name": "name"}
        if arg.lower() in col_map:
            new_key = col_map[arg.lower()]
            if state.sort_key == new_key:
                state.sort_desc = not state.sort_desc
            else:
                state.sort_key = new_key
                state.sort_desc = True
            state.scroll_offset = 0
            state.status_message = f"Sorted by {arg} ({'desc' if state.sort_desc else 'asc'})"
        else:
            state.status_message = "Usage: sort [pid|cpu|mem|name]"
        return
    
    if cmd == "filter":
        state.filter_text = arg
        state.scroll_offset = 0
        state.status_message = f"Filter: '{arg}'" if arg else "Filter cleared"
        return
    
    if cmd == "export":
        try:
            filename = arg if arg else "processes.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"PID\tNAME\tCPU%\tMEM%\tSTATUS\tUSER\n")
                for p in state.processes:
                    f.write(f"{p['pid']}\t{p['name']}\t{p['cpu_percent']:.1f}\t{p['memory_percent']:.1f}\t{p['status']}\t{p['username']}\n")
            state.status_message = f"Exported to {filename}"
        except Exception as e:
            state.status_message = f"Export failed: {e}"
        return
    
    if cmd not in ["kill", "suspend", "resume", "info"]:
        state.status_message = f"Unknown: {cmd}"
        return
    
    if not arg:
        state.status_message = f"Usage: {cmd} <pid|name>"
        return
    
    targets = []
    is_pid_lookup = arg.isdigit()
    
    if is_pid_lookup:
        try:
            targets.append(psutil.Process(int(arg)))
        except psutil.NoSuchProcess:
            state.status_message = f"PID {arg} not found"
            return
    else:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if arg.lower() in proc.info['name'].lower():
                    targets.append(psutil.Process(proc.info['pid']))
            except:
                pass
    
    if not targets:
        state.status_message = f"No process: '{arg}'"
        return
    
    if cmd == "info":
        p = targets[0]
        try:
            info = f"{p.name()} PID:{p.pid} {p.status()} CPU:{p.cpu_percent():.1f}%"
            try:
                info += f" Exe:{p.exe()[:40]}"
            except:
                pass
            state.status_message = info
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            state.status_message = "Process info unavailable"
        return
    
    protected = ["system", "registry", "memcompression", "secure system", "csrss.exe", "smss.exe", "lsass.exe", "wininit.exe", "services.exe", "winlogon.exe", "svchost.exe", "dwm.exe", "fontdrvhost.exe", "logonui.exe"]
    warn_protected = ["explorer.exe", "spoolsv.exe", "audiodg.exe"]
    
    warn_targets = []
    for p in targets:
        try:
            pname = p.name().lower()
            if pname in warn_protected:
                warn_targets.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if warn_targets and cmd in ["kill", "suspend"]:
        names = ", ".join(set(p.name() for p in warn_targets))
        state.pending_confirmation = (cmd, targets, arg)
        state.status_message = f"WARN: {names} may cause issues. {cmd.title()}? (y/n)"
        return
    
    if len(targets) > 1 and not is_pid_lookup:
        tree_info = get_process_tree_info(targets)
        preview = f"Found {len(targets)} matching '{arg}'"
        if tree_info:
            preview += f" [{tree_info[0].strip()}...]"
        state.pending_confirmation = (cmd, targets, arg)
        state.status_message = f"{preview} {cmd.title()} all? (y/n)"
        return
    
    success, errors = 0, 0
    for p in targets:
        try:
            pname = p.name().lower()
            if cmd == "kill" and pname in protected:
                state.status_message = f"Protected: {p.name()} (critical to Windows)"
                errors += 1
                continue
            
            if cmd == "kill":
                p.terminate()
                success += 1
            elif cmd == "suspend":
                p.suspend()
                success += 1
            elif cmd == "resume":
                p.resume()
                success += 1
        except psutil.AccessDenied:
            state.status_message = f"Access denied (run as Admin)"
            errors += 1
        except Exception:
            errors += 1
    
    action_names = {"kill": "Killed", "suspend": "Suspended", "resume": "Resumed"}
    state.status_message = f"{action_names[cmd]} {success}, Errors: {errors}"

def handle_input():
    """Handle keyboard input (non-blocking)."""
    while msvcrt.kbhit():
        ch = msvcrt.getwch()
        
        if state.pending_confirmation is not None:
            if ch.lower() == 'y':
                execute_pending_action()
                state.input_buffer = ""
                return
            elif ch.lower() == 'n' or ch == '\x1b':
                state.pending_confirmation = None
                state.status_message = "Action cancelled"
                state.input_buffer = ""
                return
            else:
                continue
        
        if ch in ('\x00', '\xe0'):
            if msvcrt.kbhit():
                key2 = msvcrt.getwch()
                if key2 == 'H':
                    state.scroll_offset = max(0, state.scroll_offset - 1)
                elif key2 == 'P': # Down
                    state.scroll_offset += 1
                elif key2 == 'I': # PgUp
                    state.scroll_offset = max(0, state.scroll_offset - 10)
                elif key2 == 'Q': # PgDn
                    state.scroll_offset += 10
                elif key2 == 'G': # Home
                    state.scroll_offset = 0
                elif key2 == 'O': # End
                    state.scroll_offset = max(0, len(state.processes) - 5)
                elif key2 == 'S': # Del
                    state.input_buffer = state.input_buffer[:-1]
            continue
        
        if ch == '\r':
            execute_command(state.input_buffer)
            state.input_buffer = ""
        elif ch == '\b':
            state.input_buffer = state.input_buffer[:-1]
        elif ch == '\x7f':
            state.input_buffer = state.input_buffer[:-1]
        elif ch == '\x1b':
            state.input_buffer = ""
        elif ch == '\x03':
            state.app_running = False
        elif ch.isprintable():
            state.input_buffer += ch
