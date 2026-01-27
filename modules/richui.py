#                                __    __        _____  ___  ___ 
#                               / / /\ \ \/\  /\/__   \/___\/ _ \
#                               \ \/  \/ / /_/ /  / /\//  // /_)/
#                                \  /\  / __  /  / / / \_// ___/ 
#                                 \/  \/\/ /_/   \/  \___/\/     
#                                                                
#            PRIMARY RENDERING MODULE, BECUASE I FOUND OUT ABOUT RICH 10 MINUTES AGO

import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from rich.layout import Layout
from rich.live import Live

from .state import state
from .config import REFRESH_RATES
from .utils import get_terminal_size, format_bytes, clear_screen

# Create console - force terminal mode for proper rendering
console = Console(force_terminal=True, highlight=False)

# Styles matching the original color scheme - using darker backgrounds
STYLE_RED = Style(color="bright_red", bold=True)
STYLE_GREEN = Style(color="bright_green")
STYLE_YELLOW = Style(color="bright_yellow")
STYLE_BLUE = Style(color="bright_blue")
STYLE_MAGENTA = Style(color="bright_magenta")
STYLE_CYAN = Style(color="bright_cyan")
STYLE_DIM = Style(color="grey50")
STYLE_BOLD = Style(bold=True)
STYLE_HEADER_BG = Style(bgcolor="grey15", bold=True)
STYLE_DARK_BG = Style(bgcolor="grey7")
STYLE_BAR_EMPTY = Style(color="grey30")  # Darker empty bar portions

# Startup splash messages
STARTUP_MESSAGES = [
    "Initializing terminal magic...",
    "Poking the system kernel...",
    "Interrogating your CPU...",
    "Snooping on your storage...",
    "Waking up the GPU...",
    "Collecting process breadcrumbs...",
    "Priming the performance counters...",
    "Polishing the UI...",
    "Reordering electrons...",
    "Compiling bitstreams...",
    "Calibrating flux capacitor...",
    "Reticulating splines...",
]


def get_color_for_percent(percent: float) -> Style:
    """Return appropriate color style based on percentage."""
    if percent > 90:
        return STYLE_RED
    elif percent > 70:
        return STYLE_YELLOW
    return STYLE_GREEN


def draw_rich_bar(percent: float, width: int = 20, color: Style = STYLE_GREEN) -> Text:
    """Draw a colored progress bar using Rich Text."""
    percent = max(0, min(100, percent))
    filled = int((percent / 100.0) * width)
    empty = width - filled
    
    bar = Text()
    bar.append("[")
    bar.append("█" * filled, style=color)
    bar.append("░" * empty, style=STYLE_BAR_EMPTY)  # Darker empty portion
    bar.append("]")
    return bar


def render_startup(step: int, total_steps: int, message: str = None):
    """Render a startup splash screen with progress using Rich.
    
    Args:
        step: Current step number (0-indexed)
        total_steps: Total number of steps
        message: Optional custom message, otherwise uses STARTUP_MESSAGES
    """
    cols, rows, _ = get_terminal_size()
    
    # Calculate progress
    progress = min(100, int((step / max(1, total_steps)) * 100))
    
    # Get message
    if message is None:
        msg_idx = min(step, len(STARTUP_MESSAGES) - 1)
        message = STARTUP_MESSAGES[msg_idx]
    
    # ASCII art logo - use regular strings with proper escaping
    logo_lines = [
        "   __    __        _____  ___  ___ ",
        "  / / /\\ \\ \\/\\  /\\/__   \\/___\\/ _ \\\\",
        "  \\ \\/  \\/ / /_/ /  / /\\//  // /_)/",
        "   \\  /\\  / __  /  / / / \\_// ___/ ",
        "    \\/  \\/\\/ /_/   \\/  \\___/\\/     ",
    ]
    
    # Build output buffer to prevent flicker
    output = Text()
    
    # Calculate vertical centering
    content_height = len(logo_lines) + 6
    top_padding = max(0, (rows - content_height) // 2)
    
    # Add top padding
    for _ in range(top_padding):
        output.append("\n")
    
    # Add logo (centered manually)
    for line in logo_lines:
        pad = max(0, (cols - len(line)) // 2)
        output.append(" " * pad)
        output.append(line, style="bold cyan")
        output.append("\n")
    
    output.append("\n\n")
    
    # Progress bar
    bar_width = min(50, cols - 20)
    filled = int((progress / 100) * bar_width)
    empty = bar_width - filled
    
    bar_pad = max(0, (cols - bar_width - 10) // 2)
    output.append(" " * bar_pad)
    output.append("[")
    output.append("█" * filled, style="bright_green")
    output.append("░" * empty, style="grey30")
    output.append(f"] {progress:3d}%", style="bold")
    output.append("\n\n")
    
    # Message (centered)
    msg_pad = max(0, (cols - len(message)) // 2)
    output.append(" " * msg_pad)
    output.append(message, style="bright_yellow")
    
    # Render with proper positioning - move home, print, flush
    sys.stdout.write("\033[H")  # Cursor home
    console.print(output, end="")
    sys.stdout.write("\033[J")  # Clear to end of screen
    sys.stdout.flush()


def render():
    """Render the entire UI using Rich."""
    cols, rows, toosmall = get_terminal_size()
    
    # Detect terminal resize - do a FULL screen clear to prevent artifacts
    if (cols, rows) != state.prev_term_size:
        # Full screen clear via utils (includes scrollback clear)
        clear_screen()
        state.prev_term_size = (cols, rows)
    
    # Detect if the terminal is too small
    if toosmall:
        state.status_message = "Window too small!"
    
    # Build output text buffer
    output = Text()
    
    # Hardware Info
    gpu_name_short = state.sys_stats['gpu_name'][:25] if state.sys_stats['gpu_available'] else "No GPU"
    cpu_name_short = state.sys_stats['cpu_name'][:35]
    
    header_content = f" CPU: {cpu_name_short}  |  GPU: {gpu_name_short} "
    padding_len = max(0, cols - len(header_content))
    
    header_line = Text()
    header_line.append(header_content + " " * padding_len, style=STYLE_HEADER_BG)
    output.append(header_line)
    output.append("\n")
    
    # Command Bar
    speed_indicator = f"[{state.current_refresh_rate}]"
    cmd_display = f" > {state.input_buffer}"
    vis_len = len(cmd_display) + len(speed_indicator) + 1
    padding = max(0, cols - vis_len)
    
    cmd_line = Text()
    cmd_line.append(cmd_display, style=STYLE_DARK_BG)
    cmd_line.append(" " * padding, style=STYLE_DARK_BG)
    cmd_line.append(speed_indicator + " ", style=Style(color="grey50", bgcolor="grey7"))
    output.append(cmd_line)
    output.append("\n")
    
    # Separator
    output.append(Text("─" * cols, style=STYLE_DIM))
    output.append("\n")
    
    # System Monitor
    max_sys_mon_lines = max(1, rows - 7)
    sys_lines_count = 0
    
    cpu_cores = state.sys_stats.get("cpu_per_core", [])
    mem = state.sys_stats.get("mem")
    swap = state.sys_stats.get("swap")
    disk = state.sys_stats.get("disk_usage")
    
    # Party mode magnitudes
    party_mags = None
    if state.party_mode and state.party_visualizer:
        party_mags = state.party_visualizer.get_magnitudes()
    
    # CPU bars: 3 per row
    cores_per_row = 3
    max_width_total = (cols - 45) // cores_per_row
    bar_width = max(3, min(25, max_width_total))
    
    row_text = Text()
    for i, usage in enumerate(cpu_cores):
        # New row?
        if i % cores_per_row == 0 and i > 0:
            output.append(row_text)
            output.append("\n")
            row_text = Text()
            sys_lines_count += 1
            
            if sys_lines_count >= max_sys_mon_lines - 4:
                output.append(Text(f"  ... and {len(cpu_cores) - i} more cores ...", style=STYLE_DIM))
                output.append("\n")
                break
        
        # Use party mode values if active
        if party_mags and i < len(party_mags['cpu']):
            usage = party_mags['cpu'][i]
        
        color = get_color_for_percent(usage)
        row_text.append(f"CPU{i:<2}")
        row_text.append_text(draw_rich_bar(usage, bar_width, color))
        row_text.append(f"{usage:5.1f}%  ")
    
    if row_text:
        output.append(row_text)
        output.append("\n")
    
    # Main bar width for Total/Mem/Disk etc
    main_bar_width = max(3, cols - 50)
    
    # Total CPU
    total_cpu = state.sys_stats.get("cpu_total", 0)
    if party_mags:
        total_cpu = sum(party_mags['cpu']) / len(party_mags['cpu']) if party_mags['cpu'] else 0
    
    total_line = Text()
    total_line.append("Total ", style=STYLE_BOLD)
    total_line.append_text(draw_rich_bar(total_cpu, main_bar_width, get_color_for_percent(total_cpu)))
    total_line.append(f" {total_cpu:5.1f}%")
    output.append(total_line)
    output.append("\n")
    
    # Memory
    if mem:
        mem_pct = party_mags['ram'] if party_mags else mem.percent
        mem_line = Text()
        mem_line.append("Mem   ")
        mem_line.append_text(draw_rich_bar(mem_pct, main_bar_width, STYLE_CYAN))
        mem_line.append(f" {mem_pct:5.1f}%  {format_bytes(mem.used, '')} / {format_bytes(mem.total, '')}")
        output.append(mem_line)
        output.append("\n")
    
    # Swap/Page
    if swap:
        swap_pct = party_mags['swap'] if party_mags else swap.percent
        swap_line = Text()
        swap_line.append("Page  ")
        swap_line.append_text(draw_rich_bar(swap_pct, main_bar_width, STYLE_MAGENTA))
        swap_line.append(f" {swap_pct:5.1f}%  {format_bytes(swap.used, '')} / {format_bytes(swap.total, '')}")
        output.append(swap_line)
        output.append("\n")
    
    # Disk C:
    if disk:
        disk_pct = party_mags['disk'] if party_mags else disk.percent
        disk_line = Text()
        disk_line.append("C:    ")
        disk_line.append_text(draw_rich_bar(disk_pct, main_bar_width, STYLE_BLUE))
        disk_line.append(f" {disk_pct:5.1f}%  SMART: {state.sys_stats.get('smart', '?')}")
        output.append(disk_line)
        output.append("\n")
    
    # All drives
    if state.show_all_drives:
        all_disks = state.sys_stats.get("all_disks", [])
        for letter, usage in all_disks:
            if letter.upper() != 'C:':
                drive_line = Text()
                drive_line.append(f"{letter:<5} ")
                drive_line.append_text(draw_rich_bar(usage.percent, main_bar_width, STYLE_BLUE))
                drive_line.append(f" {usage.percent:5.1f}%  {format_bytes(usage.used, '')} / {format_bytes(usage.total, '')}")
                output.append(drive_line)
                output.append("\n")
    
    # GPU
    if state.sys_stats.get("gpu_available"):
        is_igpu = state.sys_stats.get("gpu_is_igpu", False)
        gpu_line = Text()
        if is_igpu:
            gpu_line.append("GPU   ")
            gpu_line.append("[iGPU]", style=STYLE_DIM)
            gpu_line.append(f" {state.sys_stats.get('gpu_name', 'Unknown')[:30]}  ")
            gpu_line.append("(Shared Memory)", style=STYLE_CYAN)
        else:
            gpu_util = state.sys_stats.get("gpu_util", 0)
            gpu_line.append("GPU   ")
            gpu_line.append_text(draw_rich_bar(gpu_util, main_bar_width, get_color_for_percent(gpu_util)))
            gpu_line.append(f" {gpu_util:5.1f}%")
            
            gpu_mem_total = state.sys_stats.get("gpu_mem_total", 0)
            gpu_mem_used = state.sys_stats.get("gpu_mem_used", 0)
            if gpu_mem_total > 0:
                vram_pct = (gpu_mem_used / gpu_mem_total) * 100
                gpu_line.append(f"  VRAM: {format_bytes(gpu_mem_used, '')} / {format_bytes(gpu_mem_total, '')} ({vram_pct:.0f}%)")
        
        output.append(gpu_line)
        output.append("\n")
    
    # Network I/O
    net_io_line = Text()
    net_io_line.append("Net: ")
    net_io_line.append(f"↑{format_bytes(state.sys_stats.get('net_up', 0))}", style=STYLE_GREEN)
    net_io_line.append("  ")
    net_io_line.append(f"↓{format_bytes(state.sys_stats.get('net_down', 0))}", style=STYLE_CYAN)
    net_io_line.append("  │  ")
    net_io_line.append(f"I/O: R:{format_bytes(state.sys_stats.get('disk_io_read', 0))} W:{format_bytes(state.sys_stats.get('disk_io_write', 0))}")
    output.append(net_io_line)
    output.append("\n")
    
    # Separator
    output.append(Text("─" * cols, style=STYLE_DIM))
    output.append("\n")
    
    # Process Table Header
    # Calculate space for processes
    # Count lines used so far (approx from output string)
    lines_used = str(output).count('\n') + 3  # +header +status +safety
    max_proc_rows = max(1, rows - lines_used)
    
    max_scroll = max(0, len(state.processes) - max_proc_rows)
    state.scroll_offset = max(0, min(state.scroll_offset, max_scroll))
    
    # Sort indicators
    sort_ind = {"pid": "", "name": "", "cpu_percent": "", "memory_percent": ""}
    if state.sort_key in sort_ind:
        sort_ind[state.sort_key] = "▼" if state.sort_desc else "▲"
    
    header_plain = f"{'PID':<7}{sort_ind['pid']}{'NAME':<26}{sort_ind['name']}{'CPU%':<9}{sort_ind['cpu_percent']}{'MEM%':<9}{sort_ind['memory_percent']}{'STATUS':<11}{'USER':<12}"
    header_pad = max(0, cols - len(header_plain))
    
    proc_header = Text()
    proc_header.append(header_plain + " " * header_pad, style=STYLE_HEADER_BG)
    output.append(proc_header)
    output.append("\n")
    
    # Process Rows
    visible = state.processes[state.scroll_offset:state.scroll_offset + max_proc_rows]
    for p in visible:
        pid = str(p.get('pid', 0)).ljust(8)
        
        # Handle procfull mode display
        name_str = p.get('name', 'Unknown')[:25]
        child_count = p.get('_child_count', 0)
        if child_count > 0:
            name_str = f"{name_str[:20]} [+{child_count}]"
        name = name_str.ljust(27)
        
        c_val = p.get('cpu_percent', 0)
        c_str = f"{c_val:5.1f}".ljust(10)
        
        m_str = f"{p.get('memory_percent', 0):5.1f}".ljust(10)
        st = (p.get('status', '?')[:10]).ljust(11)
        us = (p.get('username', '?')[:11]).ljust(12)
        
        row_text = Text()
        row_text.append(pid)
        row_text.append(name)
        
        if c_val > 50:
            row_text.append(c_str, style=STYLE_RED)
        elif c_val > 20:
            row_text.append(c_str, style=STYLE_YELLOW)
        else:
            row_text.append(c_str)
        
        row_text.append(m_str)
        row_text.append(st)
        row_text.append(us)
        
        output.append(row_text)
        output.append("\n")
    
    # Fill remaining rows
    for _ in range(max_proc_rows - len(visible)):
        output.append("\n")
    
    # Separator
    output.append(Text("─" * cols, style=STYLE_DIM))
    output.append("\n")
    
    # Status Line
    scroll_info = f"[{state.scroll_offset + 1}-{min(state.scroll_offset + max_proc_rows, len(state.processes))}/{len(state.processes)}]"
    filter_info = f" Filter:'{state.filter_text}'" if state.filter_text else ""
    procfull_info = " [PROCFULL]" if getattr(state, 'procfull_mode', False) else ""
    
    status_msg = state.status_message
    if len(status_msg) > cols - 40:
        status_msg = status_msg[:cols - 40] + "..."
    
    status_line = Text()
    status_line.append("Status:", style=STYLE_BOLD)
    status_line.append(f" {status_msg}  {scroll_info}{filter_info}{procfull_info}")
    output.append(status_line)
    
    # Render to terminal
    # Move cursor to home position and print
    sys.stdout.write("\033[H")  # ESC[H = cursor home
    console.print(output, end="")
    sys.stdout.write("\033[J")  # Clear from cursor to end of screen
    sys.stdout.flush()
