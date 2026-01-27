#                                __    __        _____  ___  ___ 
#                               / / /\ \ \/\  /\/__   \/___\/ _ \
#                               \ \/  \/ / /_/ /  / /\//  // /_)/
#                                \  /\  / __  /  / / / \_// ___/ 
#                                 \/  \/\/ /_/   \/  \___/\/     
#                                                                
#           PSUTIL IS STILL UTIL HERE, MAINLY FOR GENERAL INFORMATION LIKE DRIVES OR CPU.

import psutil
import time
from .state import state
from . import processsn

def get_processes():
    """Fetch and sort process list with accurate CPU% using native API."""
    procs = []
    now = time.time()
    num_cpus = psutil.cpu_count() or 1
    
    # Initialize prev_proc_time if not set
    if not hasattr(state, 'prev_proc_time'):
        state.prev_proc_time = now - 0.1 # dummy diff for first run
    
    interval = now - state.prev_proc_time
    state.prev_proc_time = now

    # Get native snapshot
    try:
        snapshot = processsn.get_native_process_snapshot()
    except Exception as e:
        print(f"Native snapshot failed: {e}")
        import traceback
        traceback.print_exc()
        # Fallback if native fails (unlikely)
        return

    # Compute CPU deltas (updates state.proc_cpu_cache in-place)
    # state.proc_cpu_cache must be a dict
    if not isinstance(state.proc_cpu_cache, dict):
        state.proc_cpu_cache = {}
        
    proc_list = processsn.compute_cpu_deltas(state.proc_cpu_cache, snapshot, interval, num_cpus)
    
    # Get memory total for % calc
    try:
        mem_total = psutil.virtual_memory().total
    except:
        mem_total = 0

    # Process list into UI format
    for p in proc_list:
        pid = p['pid']
        if pid == 0: continue # Idle process

        # Calculate memory percent
        rss = p.get('rss_bytes', 0)
        mem_pct = (rss / mem_total * 100) if mem_total > 0 else 0.0
        
        # Apply filter
        name = p.get('name', '').lower()
        if state.filter_text and state.filter_text.lower() not in name:
            continue
            
        # Add to display list
        # Status and Username are expensive to fetch per-process, so we skip or cache?
        # For now, to meet "faster process calling" goal, we leave them simple or optional.
        # If we really need them, we could use psutil.Process(pid) but that defeats the optimization.
        # We'll use '?' to indicate optimized mode lacking this detail, or maybe cache it later.
        
        pinfo = {
            'pid': pid,
            'ppid': p.get('ppid', 0),  # For procfull aggregation
            'name': p['name'],
            'cpu_percent': p['cpu_percent'],
            'memory_percent': mem_pct,
            'status': 'Running', # assume running
            'username': '?'
        }
        
        procs.append(pinfo)
    
    # Aggregate children into parents if procfull_mode is enabled
    if state.procfull_mode:
        procs = aggregate_children(procs)
    
    # Sort
    try:
        if state.sort_key == 'name':
            state.processes = sorted(procs, key=lambda p: (p.get(state.sort_key) or '').lower(), reverse=state.sort_desc)
        else:
            state.processes = sorted(procs, key=lambda p: p.get(state.sort_key, 0) or 0, reverse=state.sort_desc)
    except:
        state.processes = procs


def aggregate_children(proc_list):
    """When procfull_mode is True, aggregate DIRECT child stats into parent entries.
    
    This groups processes by their parent, sums CPU/MEM of DIRECT children only
    into the parent, and marks parents with a child count indicator.
    
    Note: Only direct children are aggregated, not all descendants recursively.
    This matches typical task manager behavior where e.g., chrome.exe shows
    its immediate child processes, not the entire tree.
    """
    # Build a pid -> process info map
    pid_map = {p['pid']: p for p in proc_list}
    
    # Build parent -> direct children map
    children_map = {}  # parent_pid -> [child_pinfo, ...]
    child_pids = set()  # Track which pids are children (to exclude from result)
    
    for p in proc_list:
        ppid = p.get('ppid', 0)
        # Only consider as child if parent exists in our list and isn't self
        if ppid in pid_map and ppid != p['pid']:
            if ppid not in children_map:
                children_map[ppid] = []
            children_map[ppid].append(p)
            child_pids.add(p['pid'])
    
    # Build result: only parent processes (those not appearing as children)
    # or processes with no parent in the list
    aggregated = []
    
    for p in proc_list:
        pid = p['pid']
        
        # Skip processes that are children of another process in the list
        if pid in child_pids:
            continue
        
        # Get direct children of this process
        direct_children = children_map.get(pid, [])
        
        if direct_children:
            # Aggregate direct children stats
            child_cpu = sum(c.get('cpu_percent', 0) for c in direct_children)
            child_mem = sum(c.get('memory_percent', 0) for c in direct_children)
            
            agg_entry = p.copy()
            agg_entry['cpu_percent'] = p.get('cpu_percent', 0) + child_cpu
            agg_entry['memory_percent'] = p.get('memory_percent', 0) + child_mem
            agg_entry['_child_count'] = len(direct_children)
            aggregated.append(agg_entry)
        else:
            # No children, just add as-is
            aggregated.append(p)
    
    return aggregated


def get_process_tree_info(targets):
    """Build process tree info showing parent-child relationships."""
    tree_lines = []
    parent_groups = {}  # parent_pid -> list of child processes
    
    # targets consists of process info dicts (including 'ppid') from the native snapshot
    # instead of psutil.Process objects to maintain performance and consistency.
    for p in targets:
        # p is dict
        try:
            pid = p['pid']
            ppid = p.get('ppid', 0)
            
            if ppid not in parent_groups:
                parent_groups[ppid] = []
            parent_groups[ppid].append(p)
        except:
            pass
            
    # Map pid -> name
    proc_map = {proc['pid']: proc['name'] for proc in state.processes}

    for ppid, children in parent_groups.items():
        parent_name = proc_map.get(ppid, "unknown")
        
        for child in children:
            tree_lines.append(f"  PID {child['pid']} (parent: {ppid} {parent_name})")
    
    return tree_lines
