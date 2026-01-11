"""Utility functions module"""
import os
from .config import *

def get_terminal_size():
    """Get terminal dimensions."""
    try:
        size = os.get_terminal_size()
        if size.columns < 79 or size.lines < 18:
            return size.columns, size.lines, True
        else:
            return size.columns, size.lines, False
    except:
        return 100, 30, False

def draw_bar(percent, width=20, color=C_GREEN, empty_char="░", fill_char="█"):
    """Draw a colored progress bar."""
    percent = max(0, min(100, percent))
    filled = int((percent / 100.0) * width)
    empty = width - filled
    return f"[{color}{fill_char * filled}{C_DIM}{empty_char * empty}{C_RESET}]"

def format_bytes(b, suffix="/s"):
    """Format bytes to human readable."""
    b = abs(b)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if b < 1024.0:
            return f"{b:6.1f} {unit}{suffix}"
        b /= 1024.0
    return f"{b:6.1f} TB{suffix}"
