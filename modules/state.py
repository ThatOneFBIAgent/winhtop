"""Global state container"""

class AppState:
    def __init__(self):
        self.app_running = True
        self.input_buffer = ""
        self.status_message = "Type 'help' for commands. Use ↑↓ to scroll."
        
        # Display settings
        self.sort_key = "cpu_percent"
        self.sort_desc = True
        self.scroll_offset = 0
        self.filter_text = ""
        self.show_all_drives = False
        self.current_refresh_rate = "slow"
        
        # Data
        self.processes = []
        self.sys_stats = {
            "cpu_total": 0.0,
            "cpu_per_core": [],
            "mem": None,
            "swap": None,
            "disk_usage": None,
            "all_disks": [],
            "disk_io_read": 0.0,
            "disk_io_write": 0.0,
            "net_up": 0.0,
            "net_down": 0.0,
            "smart": "Checking...",
            "cpu_name": "Unknown CPU",
            "disk_name": "Unknown Disk",
            "gpu_name": "Unknown GPU",
            "gpu_util": 0.0,
            "gpu_mem_used": 0,
            "gpu_mem_total": 0,
            "gpu_available": False,
            "gpu_is_igpu": False
        }
        
        # Internal tracking
        self.prev_net = None
        self.prev_disk = None
        self.prev_time = 0
        self.smart_cache = ("Checking...", 0)
        self.gpu_cache = (None, 0)
        self.prev_term_size = (0, 0)
        self.hw_info_fetched = False
        self.proc_cpu_cache = {}  # pid -> (last_cpu_times, last_time)
        
        # Confirmation workflow
        self.pending_confirmation = None # (action, targets, original_arg)
        
        # Party Mode
        self.party_mode = False
        self.party_visualizer = None
        self.party_prev_refresh_rate = None

# Singleton instance
state = AppState()
