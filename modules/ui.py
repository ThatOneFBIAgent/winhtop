"""UI rendering module"""
import sys
from .state import state
from .config import *
from .utils import get_terminal_size, draw_bar, format_bytes

def render():
    """Render the entire UI."""
    cols, rows = get_terminal_size()
    
    # Detect terminal resize
    if (cols, rows) != state.prev_term_size:
        sys.stdout.write("\033[2J")
        state.prev_term_size = (cols, rows)
    
    # Validation for extremely small windows to prevent crash
    if cols < 79 or rows < 18:
        return
    
    # We build the buffer line by line.
    lines = []
    
    # --- Helper to add a line with safe ANSI handling ---
    def add_line(text, bg_color=None):
        if bg_color:
            lines.append(f"{bg_color}{text}{C_RESET}\033[K")
        else:
            lines.append(f"{text}{C_RESET}\033[K")

    # --- Header: Hardware Info ---
    gpu_name_short = state.sys_stats['gpu_name'][:25] if state.sys_stats['gpu_available'] else "No GPU"
    cpu_name_short = state.sys_stats['cpu_name'][:35]
    
    header_content = f" CPU: {cpu_name_short}  |  GPU: {gpu_name_short} "
    padding_len = max(0, cols - len(header_content)) # approx check
    lines.append(f"{C_BG_HEADER}{C_BOLD}{header_content}{' ' * padding_len}{C_RESET}")
    
    # --- Command Bar ---
    speed_indicator = f"[{state.current_refresh_rate}]"
    cmd_display = f" > {state.input_buffer}"
    vis_len = len(cmd_display) + len(speed_indicator) + 1 
    padding = max(0, cols - vis_len)
    
    lines.append(f"{C_BG_DARK}{C_BOLD}{cmd_display}{' ' * padding}{C_DIM}{speed_indicator} {C_RESET}")
    
    lines.append(f"{C_DIM}{'─' * cols}{C_RESET}\033[K")
    
    # --- System Monitor ---
    # Reserve header(3), footer(header+status+sep=3), min_proc(1) -> 7 lines reserved.
    max_sys_mon_lines = max(1, rows - 7)
    sys_mon_lines = []
    
    cpu_cores = state.sys_stats.get("cpu_per_core", [])
    mem = state.sys_stats.get("mem")
    swap = state.sys_stats.get("swap")
    disk = state.sys_stats.get("disk_usage")
    
    party_mags = None
    if state.party_mode and state.party_visualizer:
        party_mags = state.party_visualizer.get_magnitudes()
    
    # CPU bars: 3 per row
    cores_per_row = 3
    # Labels+Val per core ~ 6 + 8 = 14
    # Total overhead ~ 14*3 = 42. buffer ~3 -> 45
    max_width_total = (cols - 45) // cores_per_row
    bar_width = max(3, min(25, max_width_total))
    
    row_str = ""
    for i, usage in enumerate(cpu_cores):
        # New row start?
        if i % cores_per_row == 0 and i > 0:
            sys_mon_lines.append(row_str + "\033[K")
            row_str = ""
            
            # Check overflow
            if len(sys_mon_lines) >= max_sys_mon_lines - 4: # Leave room for Total/Mem/Disk/Page
                 sys_mon_lines.append(f"{C_DIM}  ... and {len(cpu_cores) - i} more cores ...{C_RESET}\033[K")
                 break
        
        if party_mags and i < len(party_mags['cpu']):
            usage = party_mags['cpu'][i]
        
        color = C_GREEN
        if usage > 70: color = C_YELLOW
        if usage > 90: color = C_RED
        
        row_str += f"CPU{i:<2}{draw_bar(usage, bar_width, color)}{usage:5.1f}%  "
    
    if row_str:
        sys_mon_lines.append(row_str + "\033[K")
    
    # Total CPU
    total_cpu = state.sys_stats.get("cpu_total", 0)
    if party_mags:
        total_cpu = sum(party_mags['cpu']) / len(party_mags['cpu']) if party_mags['cpu'] else 0
    total_color = C_GREEN
    if total_cpu > 70: total_color = C_YELLOW
    if total_cpu > 90: total_color = C_RED
    
    # Main Bars calculation
    # "Label " (6) + [bar] (w+2) + " " (1) + "100.0%" (6) + "  " (2) + "xxx GB / xxx GB" (25ish)
    # Total overhead ~ 6 + 2 + 1 + 6 + 2 + 25 = 42 chars.
    # Safe conservative: cols - 50.
    main_bar_width = max(3, cols - 50)
    
    sys_mon_lines.append(f"{C_BOLD}Total{C_RESET} {draw_bar(total_cpu, main_bar_width, total_color)} {total_cpu:5.1f}%\033[K")
    
    if mem:
        mem_pct = party_mags['ram'] if party_mags else mem.percent
        sys_mon_lines.append(f"Mem   {draw_bar(mem_pct, main_bar_width, C_CYAN)} {mem_pct:5.1f}%  {format_bytes(mem.used, '')} / {format_bytes(mem.total, '')}\033[K")
    
    if swap:
        swap_pct = party_mags['swap'] if party_mags else swap.percent
        sys_mon_lines.append(f"Page  {draw_bar(swap_pct, main_bar_width, C_MAGENTA)} {swap_pct:5.1f}%  {format_bytes(swap.used, '')} / {format_bytes(swap.total, '')}\033[K")
    
    if disk:
        disk_pct = party_mags['disk'] if party_mags else disk.percent
        sys_mon_lines.append(f"C:    {draw_bar(disk_pct, main_bar_width, C_BLUE)} {disk_pct:5.1f}%  SMART: {state.sys_stats.get('smart', '?')}\033[K")
        
    if state.show_all_drives:
        all_disks = state.sys_stats.get("all_disks", [])
        for letter, usage in all_disks:
            if letter.upper() != 'C:':
                sys_mon_lines.append(f"{letter:<5} {draw_bar(usage.percent, main_bar_width, C_BLUE)} {usage.percent:5.1f}%  {format_bytes(usage.used, '')} / {format_bytes(usage.total, '')}\033[K")

    if state.sys_stats.get("gpu_available"):
        is_igpu = state.sys_stats.get("gpu_is_igpu", False)
        if is_igpu:
            gpu_line = f"GPU   {C_DIM}[iGPU]{C_RESET} {state.sys_stats.get('gpu_name', 'Unknown')[:30]}  {C_CYAN}(Shared Memory){C_RESET}"
        else:
            gpu_util = state.sys_stats.get("gpu_util", 0)
            gpu_color = C_GREEN
            if gpu_util > 70: gpu_color = C_YELLOW
            if gpu_util > 90: gpu_color = C_RED
            
            # Additional GPU VRAM text ~ 30 chars?
            # "  VRAM: 12.0 GB / 24.0 GB (50%)" -> 30 chars.
            # Label(6) + Bar(w+2) + Pct(6) + 30 = w + 44.
            # Use main_bar_width (cols-50) is safe.
            gpu_line = f"GPU   {draw_bar(gpu_util, main_bar_width, gpu_color)} {gpu_util:5.1f}%"
            
            gpu_mem_total = state.sys_stats.get("gpu_mem_total", 0)
            gpu_mem_used = state.sys_stats.get("gpu_mem_used", 0)
            if gpu_mem_total > 0:
                vram_pct = (gpu_mem_used / gpu_mem_total) * 100
                gpu_line += f"  VRAM: {format_bytes(gpu_mem_used, '')} / {format_bytes(gpu_mem_total, '')} ({vram_pct:.0f}%)"
        
        sys_mon_lines.append(gpu_line + "\033[K")
        
    # Net I/O
    net_io_line = (
        f"Net: {C_GREEN}↑{format_bytes(state.sys_stats.get('net_up', 0))}{C_RESET}  "
        f"{C_CYAN}↓{format_bytes(state.sys_stats.get('net_down', 0))}{C_RESET}  │  "
        f"I/O: R:{format_bytes(state.sys_stats.get('disk_io_read', 0))} W:{format_bytes(state.sys_stats.get('disk_io_write', 0))}"
    )
    sys_mon_lines.append(net_io_line + "\033[K")

    # Add sys mon lines using truncated length if needed
    # Logic above handled break.
    lines.extend(sys_mon_lines)
    
    # Separator
    lines.append(f"{C_DIM}{'─' * cols}{C_RESET}\033[K")
    
    # Proc table
    # Calc space
    used_height = len(lines) + 2 # +1 header, +1 status
    max_proc_rows = max(1, rows - used_height - 1) # -1 safety
    
    max_scroll = max(0, len(state.processes) - max_proc_rows)
    state.scroll_offset = max(0, min(state.scroll_offset, max_scroll))
    
    sort_ind = {"pid": "", "name": "", "cpu_percent": "", "memory_percent": ""}
    if state.sort_key in sort_ind:
        sort_ind[state.sort_key] = "▼" if state.sort_desc else "▲"
    
    # Header
    header_plain = f"{'PID':<7}{sort_ind['pid']}{'NAME':<26}{sort_ind['name']}{'CPU%':<9}{sort_ind['cpu_percent']}{'MEM%':<9}{sort_ind['memory_percent']}{'STATUS':<11}{'USER':<12}"
    header_pad = max(0, cols - len(header_plain))
    lines.append(f"{C_BOLD}{C_BG_HEADER}{header_plain}{' ' * header_pad}{C_RESET}")
    
    # Proc Rows
    visible = state.processes[state.scroll_offset : state.scroll_offset + max_proc_rows]
    for p in visible:
        pid = str(p.get('pid', 0)).ljust(8)
        name = (p.get('name', 'Unknown')[:25]).ljust(27)
        c_val = p.get('cpu_percent', 0)
        c_str = f"{c_val:5.1f}".ljust(10)
        if c_val > 50: c_str = f"{C_RED}{c_str}{C_RESET}"
        elif c_val > 20: c_str = f"{C_YELLOW}{c_str}{C_RESET}"
        
        m_str = f"{p.get('memory_percent', 0):5.1f}".ljust(10)
        st = (p.get('status', '?')[:10]).ljust(11)
        us = (p.get('username', '?')[:11]).ljust(12)
        lines.append(f"{pid}{name}{c_str}{m_str}{st}{us}\033[K")
    
    # Fill
    for _ in range(max_proc_rows - len(visible)):
        lines.append("\033[K")
    
    lines.append(f"{C_DIM}{'─' * cols}{C_RESET}\033[K")
    
    # Status
    scroll_info = f"[{state.scroll_offset + 1}-{min(state.scroll_offset + max_proc_rows, len(state.processes))}/{len(state.processes)}]"
    filter_info = f" Filter:'{state.filter_text}'" if state.filter_text else ""
    status_msg = state.status_message
    if len(status_msg) > cols - 30: status_msg = status_msg[:cols-30] + "..."
    status_line = f"{C_BOLD}Status:{C_RESET} {status_msg}  {scroll_info}{filter_info}"
    
    lines.append(status_line + "\033[K")
    
    # Truncate strictly to rows-1 to prevent scroll
    # We want to print at 0,0.
    sys.stdout.write("\033[H")
    # Join with newlines
    # Truncate to rows to prevent scroll, height math is handled above.
    # and also :rows-1 deletes the status bar.
    final_output = lines[:rows]
    
    sys.stdout.write("\n".join(final_output))
    sys.stdout.write("\033[J") # Clear remaining bottom
    sys.stdout.flush()
