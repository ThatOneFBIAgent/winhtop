"""Process info/list module"""
import psutil
import time
from .state import state

def get_processes():
    """Fetch and sort process list with accurate CPU%."""
    procs = []
    now = time.time()
    num_cpus = psutil.cpu_count() or 1
    
    new_cache = {}
    
    for proc in psutil.process_iter(['pid', 'name', 'status', 'username']):
        try:
            pid = proc.pid
            
            # Skip System Idle Process
            if pid == 0:
                continue
            
            pinfo = proc.info.copy()
            
            # Calculate CPU% properly using cpu_times delta
            try:
                cpu_times = proc.cpu_times()
                total_time = cpu_times.user + cpu_times.system
                
                if pid in state.proc_cpu_cache:
                    prev_total, prev_time = state.proc_cpu_cache[pid]
                    dt = now - prev_time
                    if dt > 0:
                        cpu_pct = ((total_time - prev_total) / dt) * 100 / num_cpus
                        cpu_pct = max(0, min(cpu_pct, 100))
                    else:
                        cpu_pct = 0.0
                else:
                    cpu_pct = 0.0
                
                new_cache[pid] = (total_time, now)
                pinfo['cpu_percent'] = cpu_pct
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pinfo['cpu_percent'] = 0.0
            
            # Memory %
            try:
                pinfo['memory_percent'] = proc.memory_percent() or 0.0
            except:
                pinfo['memory_percent'] = 0.0
            
            # Clean up username
            if pinfo.get('username'):
                pinfo['username'] = pinfo['username'].split('\\')[-1]
            else:
                pinfo['username'] = '?'
            
            # Apply filter
            if state.filter_text:
                name = pinfo.get('name', '').lower()
                if state.filter_text.lower() not in name:
                    continue
            
            procs.append(pinfo)
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    state.proc_cpu_cache = new_cache
    
    # Sort
    try:
        if state.sort_key == 'name':
            state.processes = sorted(procs, key=lambda p: (p.get(state.sort_key) or '').lower(), reverse=state.sort_desc)
        else:
            state.processes = sorted(procs, key=lambda p: p.get(state.sort_key, 0) or 0, reverse=state.sort_desc)
    except:
        state.processes = procs

def get_process_tree_info(targets):
    """Build process tree info showing parent-child relationships."""
    tree_lines = []
    parent_groups = {}  # parent_pid -> list of child processes
    
    for p in targets:
        try:
            ppid = p.ppid()
            if ppid not in parent_groups:
                parent_groups[ppid] = []
            parent_groups[ppid].append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            if 0 not in parent_groups:
                parent_groups[0] = []
            parent_groups[0].append(p)
    
    for ppid, children in parent_groups.items():
        parent_name = "unknown"
        try:
            if ppid > 0:
                parent_proc = psutil.Process(ppid)
                parent_name = parent_proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        for child in children:
            try:
                tree_lines.append(f"  PID {child.pid} (parent: {ppid} {parent_name})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    
    return tree_lines
