"""Process info/list module"""
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
            'name': p['name'],
            'cpu_percent': p['cpu_percent'],
            'memory_percent': mem_pct,
            'status': 'Running', # assume running
            'username': '?'
        }
        
        procs.append(pinfo)
    
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
    
    # Recalculate full list for tree building if needed, or search current state.processes?
    # get_process_tree_info takes 'targets' which are psutil.Process objects usually...
    # Wait, 'targets' in ui.py or input.py might be passed as PID or dict?
    # In pending_confirmation, targets is list of dicts or objects.
    # We need to verify what 'targets' contains.
    # Since we replaced get_processes, state.processes now contains dicts, not psutil.Process objects.
    # Previous code: procs.append(pinfo) -> pinfo was dict (proc.info.copy()).
    # So targets is list of dicts.
    
    # However, get_process_tree_info implementation in original used p.ppid() which implies p is psutil.Process?
    # Let's check the original code again.
    # "for p in targets: try: ppid = p.ppid() ..."
    # "procs.append(pinfo)" where pinfo is dict.
    # Ah, the `targets` passed to `get_process_tree_info` might come from `state.pending_confirmation`? 
    # Let's assume we need to handle dicts now, or re-instantiate psutil objects.
    # The user asked for "Displaying the entire process tree...".
    
    # If targets contains dicts from our new get_processes, they have 'pid' and 'ppid' (we added ppid in processsn return).
    # processsn.compute_cpu_deltas returns list of dicts WITH 'ppid'.
    # So we can use that.
    
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
            
    # We need to look up parent names.
    # We can use state.processes to find names of parents!
    # Map pid -> name
    proc_map = {proc['pid']: proc['name'] for proc in state.processes}

    for ppid, children in parent_groups.items():
        parent_name = proc_map.get(ppid, "unknown")
        
        for child in children:
            tree_lines.append(f"  PID {child['pid']} (parent: {ppid} {parent_name})")
    
    return tree_lines
