"""Hardware info module"""
import psutil
import time
import subprocess
import sys
from .state import state
from .config import *

# GPU Detection (cached)
def get_gpu_info():
    """Get GPU info - handles NVIDIA discrete, AMD iGPU, and Intel iGPU."""
    now = time.time()
    
    # Return cached value if fresh
    if state.gpu_cache[0] is not None and now - state.gpu_cache[1] < 2:
        return state.gpu_cache[0]
    
    gpu_stats = {
        "name": "Unknown GPU",
        "util": 0.0,
        "mem_used": 0,
        "mem_total": 0,
        "available": False,
        "is_igpu": False  # True for integrated graphics (AMD G / Intel)
    }
    
    # Try nvidia-smi first (discrete NVIDIA GPU)
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used,memory.total',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(',')
            if len(parts) >= 4:
                gpu_stats["name"] = parts[0].strip()[:40]
                gpu_stats["util"] = float(parts[1].strip())
                gpu_stats["mem_used"] = int(float(parts[2].strip())) * 1024 * 1024  # MB to bytes
                gpu_stats["mem_total"] = int(float(parts[3].strip())) * 1024 * 1024
                gpu_stats["available"] = True
                gpu_stats["is_igpu"] = False
                state.gpu_cache = (gpu_stats, now)
                return gpu_stats
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    
    # Fallback: PowerShell WMI for GPU name
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             '(Get-CimInstance Win32_VideoController | Select-Object -First 1).Name'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_name = result.stdout.strip()[:40]
            gpu_stats["name"] = gpu_name
            gpu_stats["available"] = True
            
            # Detect if this is an integrated GPU
            gpu_name_lower = gpu_name.lower()
            
            # Intel integrated graphics detection
            if "intel" in gpu_name_lower and "arc" not in gpu_name_lower:
                gpu_stats["is_igpu"] = True
            elif "radeon graphics" in gpu_name_lower and "rx" not in gpu_name_lower:
                gpu_stats["is_igpu"] = True
            
            # Also check CPU name for AMD APUs
            cpu_name = state.sys_stats.get("cpu_name", "")
            if cpu_name:
                import re
                match = re.search(r'\d{4}G\b', cpu_name)
                if match:
                    gpu_stats["is_igpu"] = True
            
            # For discrete GPUs (non-iGPU), try to get VRAM
            if not gpu_stats["is_igpu"]:
                vram_result = subprocess.run(
                    ['powershell', '-NoProfile', '-Command',
                     '(Get-CimInstance Win32_VideoController | Select-Object -First 1).AdapterRAM'],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if vram_result.returncode == 0 and vram_result.stdout.strip():
                    try:
                        vram = int(vram_result.stdout.strip())
                        gpu_stats["mem_total"] = vram if vram > 0 else 0
                    except ValueError:
                        pass
    except (subprocess.TimeoutExpired, Exception):
        pass
    
    state.gpu_cache = (gpu_stats, now)
    return gpu_stats

def get_hardware_info():
    """Fetch hardware info once at startup using PowerShell."""
    if state.hw_info_fetched:
        return

    ps_cmd = r'''
    $disk = Get-Volume -DriveLetter C |
        Get-Partition |
        Get-Disk |
        Select-Object -First 1

    $friendly = $disk.FriendlyName
    $model = Get-CimInstance Win32_DiskDrive |
        Where-Object { $_.Index -eq $disk.Number } |
        Select-Object -First 1 -ExpandProperty Model

    $bus  = $disk.BusType
    $size = [math]::Round($disk.Size / 1GB, 0)

    $chosen = $null
    if ($model -and $model.Trim().Length -gt $friendly.Trim().Length) {
        $chosen = $model.Trim()
    }
    elseif ($friendly) {
        $chosen = $friendly.Trim()
    }

    if (-not $chosen) {
        $chosen = "Disk $bus $size GB"
    }
    elseif ($chosen.Length -lt 8) {
        $chosen = "$chosen $bus $size GB"
    }

    $chosen
    '''

    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', 
             '(Get-CimInstance Win32_Processor).Name'],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            cpu_name = result.stdout.strip()
            if " w/" in cpu_name:
                cpu_name = cpu_name.split(" w/")[0]
            state.sys_stats["cpu_name"] = cpu_name[:50]
    except:
        try:
            import platform
            state.sys_stats["cpu_name"] = platform.processor()[:50] or "Unknown CPU"
        except:
            pass
    
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_cmd],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        name = result.stdout.strip()
        if name:
            state.sys_stats["disk_name"] = name[:40]

    except Exception as e:
        pass
    
    state.hw_info_fetched = True

def get_smart_status():
    """Get SMART/Health status via PowerShell (cached)."""
    now = time.time()
    
    if now - state.smart_cache[1] < 120:
        return state.smart_cache[0]
    
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             '(Get-PhysicalDisk | Select-Object -First 1).HealthStatus'],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        output = result.stdout.strip().lower()
        if "healthy" in output:
            status = f"{C_GREEN}Healthy{C_RESET}"
        elif "warning" in output:
            status = f"{C_YELLOW}Warning{C_RESET}"
        elif "unhealthy" in output:
            status = f"{C_RED}Unhealthy{C_RESET}"
        elif output:
            status = f"{C_YELLOW}{output[:10]}{C_RESET}"
        else:
            status = f"{C_DIM}N/A{C_RESET}"
    except subprocess.TimeoutExpired:
        status = f"{C_DIM}Timeout{C_RESET}"
    except Exception:
        status = f"{C_DIM}N/A{C_RESET}"
    
    state.smart_cache = (status, now)
    return status

def update_system_stats_fast():
    """Update only CPU stats - for high-speed rendering modes."""
    try:
        per_core = psutil.cpu_percent(percpu=True)
        state.sys_stats["cpu_per_core"] = per_core
        state.sys_stats["cpu_total"] = sum(per_core) / len(per_core) if per_core else 0
    except:
        pass

def update_system_stats_slow():
    """Update all system stats except CPU."""
    now = time.time()
    dt = now - state.prev_time if state.prev_time else 1.0
    state.prev_time = now
    
    try:
        state.sys_stats["mem"] = psutil.virtual_memory()
    except:
        pass
    
    try:
        state.sys_stats["swap"] = psutil.swap_memory()
    except:
        pass
    
    try:
        state.sys_stats["disk_usage"] = psutil.disk_usage('C:\\')
    except:
        pass
    
    try:
        all_disks = []
        for part in psutil.disk_partitions(all=False):
            if 'fixed' in part.opts.lower() or part.fstype:
                try:
                    letter = part.mountpoint.rstrip('\\')
                    usage = psutil.disk_usage(part.mountpoint)
                    all_disks.append((letter, usage))
                except (PermissionError, OSError):
                    pass
        state.sys_stats["all_disks"] = all_disks
    except:
        pass
    
    try:
        curr_disk = psutil.disk_io_counters()
        if state.prev_disk and dt > 0:
            state.sys_stats["disk_io_read"] = (curr_disk.read_bytes - state.prev_disk.read_bytes) / dt
            state.sys_stats["disk_io_write"] = (curr_disk.write_bytes - state.prev_disk.write_bytes) / dt
        state.prev_disk = curr_disk
    except:
        pass

    try:
        curr_net = psutil.net_io_counters()
        if state.prev_net and dt > 0:
            state.sys_stats["net_up"] = (curr_net.bytes_sent - state.prev_net.bytes_sent) / dt
            state.sys_stats["net_down"] = (curr_net.bytes_recv - state.prev_net.bytes_recv) / dt
        state.prev_net = curr_net
    except:
        pass

    state.sys_stats["smart"] = get_smart_status()
    
    gpu = get_gpu_info()
    state.sys_stats["gpu_name"] = gpu["name"]
    state.sys_stats["gpu_util"] = gpu["util"]
    state.sys_stats["gpu_mem_used"] = gpu["mem_used"]
    state.sys_stats["gpu_mem_total"] = gpu["mem_total"]
    state.sys_stats["gpu_available"] = gpu["available"]
    state.sys_stats["gpu_is_igpu"] = gpu.get("is_igpu", False)

def update_system_stats():
    """Update all system-level statistics."""
    update_system_stats_fast()
    update_system_stats_slow()
