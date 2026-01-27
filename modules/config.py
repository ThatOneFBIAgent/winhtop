# yeah im not putting corny shit for the single file storing constants and speeds.
# said the dumbass "iza carlos" smh - 23 / 01 / 2026

# ANSI Colors & Styling
C_RESET = "\033[0m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"
C_WHITE = "\033[97m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_BG_DARK = "\033[48;5;236m"
C_BG_HEADER = "\033[48;5;238m"

# Configuration
REFRESH_RATES = {
    "slow": 3.0,
    "medium": 2.0,
    "fast": 1.0,
    "superfast": 0.5,
    "ultrafast": 0.1,
    # so for about 60 fps:
    "party": 0.0167
}

# UI Mode Toggle - stored in registry for persistence across runs
# Uses HKEY_CURRENT_USER\Software\WinHTop\UseRichUI
import winreg

def _get_rich_ui_pref():
    """Load USE_RICH_UI from Windows registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\WinHTop", 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "UseRichUI")
        winreg.CloseKey(key)
        return bool(value)
    except (FileNotFoundError, OSError):
        return True  # Default to Rich UI

def _set_rich_ui_pref(enabled: bool):
    """Save USE_RICH_UI to Windows registry."""
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\WinHTop")
        winreg.SetValueEx(key, "UseRichUI", 0, winreg.REG_DWORD, 1 if enabled else 0)
        winreg.CloseKey(key)
    except OSError:
        pass  # Silently fail if can't write

# Load preference on import
USE_RICH_UI = _get_rich_ui_pref()
