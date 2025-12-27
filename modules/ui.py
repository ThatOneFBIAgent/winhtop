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
    
    lines = []
    
    # Header: Hardware Info
    gpu_name_short = state.sys_stats['gpu_name'][:25] if state.sys_stats['gpu_available'] else "No GPU"
    hw_line = f"{C_BG_HEADER}{C_BOLD} CPU: {state.sys_stats['cpu_name'][:35]}  |  GPU: {gpu_name_short} {C_RESET}"
    hw_line = hw_line + " " * max(0, cols - len(hw_line) + 20)
    lines.append(hw_line)
    
    # Command Bar
    speed_indicator = f"[{state.current_refresh_rate}]"
    cmd_display = f" > {state.input_buffer}"
    padding = cols - len(cmd_display) - len(speed_indicator) - 2
    cmd_line = f"{C_BG_DARK}{C_BOLD}{cmd_display}{' ' * max(0, padding)}{C_DIM}{speed_indicator} {C_RESET}"
    lines.append(cmd_line)
    
    lines.append(f"{C_DIM}{'─' * cols}{C_RESET}")
    
    # System Monitor
    cpu_cores = state.sys_stats.get("cpu_per_core", [])
    mem = state.sys_stats.get("mem")
    swap = state.sys_stats.get("swap")
    disk = state.sys_stats.get("disk_usage")
    
    party_mags = None
    if state.party_mode and state.party_visualizer:
        party_mags = state.party_visualizer.get_magnitudes()
    
    # CPU bars
    cores_per_row = 4
    bar_width = 12
    
    for row_start in range(0, len(cpu_cores), cores_per_row):
        row_cores = cpu_cores[row_start:row_start + cores_per_row]
        row_str = ""
        for i, usage in enumerate(row_cores):
            core_idx = row_start + i
            
            if party_mags and core_idx < len(party_mags['cpu']):
                usage = party_mags['cpu'][core_idx]
            
            color = C_GREEN
            if usage > 70: color = C_YELLOW
            if usage > 90: color = C_RED
            row_str += f"CPU{core_idx:<2}{draw_bar(usage, bar_width, color)}{usage:5.1f}%  "
        lines.append(row_str)
    
    total_cpu = state.sys_stats.get("cpu_total", 0)
    if party_mags:
        total_cpu = sum(party_mags['cpu']) / len(party_mags['cpu']) if party_mags['cpu'] else 0
    total_color = C_GREEN
    if total_cpu > 70: total_color = C_YELLOW
    if total_cpu > 90: total_color = C_RED
    lines.append(f"{C_BOLD}Total{C_RESET} {draw_bar(total_cpu, 25, total_color)} {total_cpu:5.1f}%")
    
    if mem:
        mem_pct = party_mags['ram'] if party_mags else mem.percent
        lines.append(f"Mem   {draw_bar(mem_pct, 25, C_CYAN)} {mem_pct:5.1f}%  {format_bytes(mem.used, '')} / {format_bytes(mem.total, '')}")
    
    if swap:
        swap_pct = party_mags['swap'] if party_mags else swap.percent
        lines.append(f"Page  {draw_bar(swap_pct, 25, C_MAGENTA)} {swap_pct:5.1f}%  {format_bytes(swap.used, '')} / {format_bytes(swap.total, '')} (Pagefile)")
    
    if disk:
        disk_pct = party_mags['disk'] if party_mags else disk.percent
        lines.append(f"C:    {draw_bar(disk_pct, 25, C_BLUE)} {disk_pct:5.1f}%  SMART: {state.sys_stats.get('smart', '?')}")
    
    if state.show_all_drives:
        all_disks = state.sys_stats.get("all_disks", [])
        for letter, usage in all_disks:
            if letter.upper() != 'C:':
                lines.append(f"{letter:<5} {draw_bar(usage.percent, 25, C_BLUE)} {usage.percent:5.1f}%  {format_bytes(usage.used, '')} / {format_bytes(usage.total, '')}")
    
    if state.sys_stats.get("gpu_available"):
        is_igpu = state.sys_stats.get("gpu_is_igpu", False)
        
        if is_igpu:
            gpu_line = f"GPU   {C_DIM}[iGPU]{C_RESET} {state.sys_stats.get('gpu_name', 'Unknown')[:30]}  {C_CYAN}(Shared Memory){C_RESET}"
        else:
            gpu_util = state.sys_stats.get("gpu_util", 0)
            gpu_color = C_GREEN
            if gpu_util > 70: gpu_color = C_YELLOW
            if gpu_util > 90: gpu_color = C_RED
            
            gpu_line = f"GPU   {draw_bar(gpu_util, 25, gpu_color)} {gpu_util:5.1f}%"
            
            gpu_mem_total = state.sys_stats.get("gpu_mem_total", 0)
            gpu_mem_used = state.sys_stats.get("gpu_mem_used", 0)
            if gpu_mem_total > 0:
                vram_pct = (gpu_mem_used / gpu_mem_total) * 100
                gpu_line += f"  VRAM: {format_bytes(gpu_mem_used, '')} / {format_bytes(gpu_mem_total, '')} ({vram_pct:.0f}%)"
        
        lines.append(gpu_line)
    
    net_io_line = (
        f"Net: {C_GREEN}↑{format_bytes(state.sys_stats.get('net_up', 0))}{C_RESET}  "
        f"{C_CYAN}↓{format_bytes(state.sys_stats.get('net_down', 0))}{C_RESET}  │  "
        f"I/O: R:{format_bytes(state.sys_stats.get('disk_io_read', 0))} W:{format_bytes(state.sys_stats.get('disk_io_write', 0))}"
    )
    lines.append(net_io_line)
    
    lines.append(f"{C_DIM}{'─' * cols}{C_RESET}")
    
    # Process Table
    header_lines = len(lines) + 3
    max_proc_rows = max(5, rows - header_lines - 1)
    
    max_scroll = max(0, len(state.processes) - max_proc_rows)
    state.scroll_offset = max(0, min(state.scroll_offset, max_scroll))
    
    sort_ind = {"pid": "", "name": "", "cpu_percent": "", "memory_percent": ""}
    if state.sort_key in sort_ind:
        sort_ind[state.sort_key] = "▼" if state.sort_desc else "▲"
    
    header = (
        f"{C_BOLD}{C_BG_HEADER}"
        f"{'PID':<7}{sort_ind['pid']}"
        f"{'NAME':<26}{sort_ind['name']}"
        f"{'CPU%':<9}{sort_ind['cpu_percent']}"
        f"{'MEM%':<9}{sort_ind['memory_percent']}"
        f"{'STATUS':<11}"
        f"{'USER':<12}"
        f"{C_RESET}"
    )
    lines.append(header)
    
    visible = state.processes[state.scroll_offset : state.scroll_offset + max_proc_rows]
    for p in visible:
        pid = str(p.get('pid', 0)).ljust(8)
        name = (p.get('name', 'Unknown')[:25]).ljust(27)
        
        cpu_val = p.get('cpu_percent', 0)
        cpu_str = f"{cpu_val:5.1f}".ljust(10)
        if cpu_val > 50: cpu_str = f"{C_RED}{cpu_str}{C_RESET}"
        elif cpu_val > 20: cpu_str = f"{C_YELLOW}{cpu_str}{C_RESET}"
        
        mem_str = f"{p.get('memory_percent', 0):5.1f}".ljust(10)
        status = (p.get('status', '?')[:10]).ljust(11)
        user = (p.get('username', '?')[:11]).ljust(12)
        
        lines.append(f"{pid}{name}{cpu_str}{mem_str}{status}{user}")
    
    for _ in range(max_proc_rows - len(visible)):
        lines.append("")
    
    lines.append(f"{C_DIM}{'─' * cols}{C_RESET}")
    
    scroll_info = f"[{state.scroll_offset + 1}-{min(state.scroll_offset + max_proc_rows, len(state.processes))}/{len(state.processes)}]"
    filter_info = f" Filter:'{state.filter_text}'" if state.filter_text else ""
    status_line = f"{C_BOLD}Status:{C_RESET} {state.status_message}  {scroll_info}{filter_info}"
    lines.append(status_line)
    
    sys.stdout.write("\033[H")
    output = "\n".join(lines)
    sys.stdout.write(output)
    sys.stdout.write("\033[J")
    sys.stdout.flush()
