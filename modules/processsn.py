"""Process info/list module using native windows APIs"""
import ctypes
import ctypes.wintypes as wt

# Windows types for NtQuerySystemInformation
ntdll = ctypes.WinDLL("ntdll")

SystemProcessInformation = 5

class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wt.WORD),
        ("MaximumLength", wt.WORD),
        ("Buffer", wt.LPWSTR)
    ]

class SYSTEM_THREAD_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("KernelTime", wt.LARGE_INTEGER),
        ("UserTime", wt.LARGE_INTEGER),
        ("CreateTime", wt.LARGE_INTEGER),
        ("WaitTime", wt.ULONG),
        ("StartAddress", wt.LPVOID),
        ("ClientId", wt.LARGE_INTEGER * 1),  # not used here
        ("Priority", wt.LONG),
        ("BasePriority", wt.LONG),
        ("ContextSwitches", wt.ULONG),
        ("ThreadState", wt.ULONG),
        ("WaitReason", wt.ULONG),
    ]

class SYSTEM_PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("NextEntryOffset", wt.ULONG),
        ("NumberOfThreads", wt.ULONG),
        ("WorkingSetPrivateSize", wt.LARGE_INTEGER),
        ("HardFaultCount", wt.ULONG),
        ("NumberOfThreadsHighWatermark", wt.ULONG),
        ("CycleTime", ctypes.c_ulonglong),
        ("CreateTime", wt.LARGE_INTEGER),
        ("UserTime", wt.LARGE_INTEGER),
        ("KernelTime", wt.LARGE_INTEGER),
        ("ImageName", UNICODE_STRING),
        ("BasePriority", wt.LONG),
        ("UniqueProcessId", wt.HANDLE),
        ("InheritedFromUniqueProcessId", wt.HANDLE),
        ("HandleCount", wt.ULONG),
        ("SessionId", wt.ULONG),
        ("UniqueProcessKey", ctypes.c_size_t),
        ("PeakVirtualSize", ctypes.c_size_t),
        ("VirtualSize", ctypes.c_size_t),
        ("PageFaultCount", wt.ULONG),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivatePageCount", ctypes.c_size_t),
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
        # Followed in memory by SYSTEM_THREAD_INFORMATION array
    ]

def get_native_process_snapshot():
    """
    Returns a list of process records using a single native Windows kernel query.

    This function performs ONE call to NtQuerySystemInformation with
    SystemProcessInformation and parses the resulting process list.

    Inputs:
        None

    Returns:
        list[dict] where each dict contains:
            pid (int)
            ppid (int)
            name (str)
            threads (int)
            user_time_100ns (int)
            kernel_time_100ns (int)
            rss_bytes (int)

    Notes:
        CPU is NOT a percent here. It must be computed using deltas across snapshots (done in processes.py, but this contains a helper).
        Time values are in 100 nanosecond units, straight from Windows.
    """

    # First call allocates a buffer guess
    buf_size = 1_000_000
    while True:
        buf = ctypes.create_string_buffer(buf_size)
        ret = ntdll.NtQuerySystemInformation(
            SystemProcessInformation,
            buf,
            buf_size,
            None
        )

        STATUS_INFO_LENGTH_MISMATCH = 0xC0000004

        if ret == STATUS_INFO_LENGTH_MISMATCH:
            # buffer too small, grow it
            buf_size *= 2
            continue

        if ret != 0:
            raise OSError("NtQuerySystemInformation failed")

        break

    results = []
    offset = 0

    while True:
        entry = ctypes.cast(
            ctypes.addressof(buf) + offset,
            ctypes.POINTER(SYSTEM_PROCESS_INFORMATION)
        ).contents

        pid = ctypes.cast(entry.UniqueProcessId, ctypes.c_void_p).value or 0
        ppid = ctypes.cast(entry.InheritedFromUniqueProcessId, ctypes.c_void_p).value or 0

        name = entry.ImageName.Buffer if entry.ImageName.Buffer else "System"

        results.append({
            "pid": pid,
            "ppid": ppid,
            "name": name,
            "threads": entry.NumberOfThreads,
            "user_time_100ns": entry.UserTime,
            "kernel_time_100ns": entry.KernelTime,
            "rss_bytes": entry.WorkingSetSize,
        })

        if entry.NextEntryOffset == 0:
            break

        offset += entry.NextEntryOffset

    return results

def compute_cpu_deltas(prev_cache, curr_snapshot, interval_seconds, cpu_count):
    """
    Computes per process CPU percent from two snapshots.

    Inputs:
        prev_cache:
            dict[int, dict]
            The EXISTING cache map of pid -> record. Will be updated in-place.

        curr_snapshot:
            list[dict]
            A fresh list from get_native_process_snapshot

        interval_seconds:
            float
            Real time elapsed between the two samples

        cpu_count:
            int
            Number of logical CPUs for normalization

    Returns:
        list[dict]:
            proc_list with computed stats
    """
    results = []

    # Clamp interval to avoid division by zero or noisy spikes on very fast updates
    if interval_seconds < 0.05:
        interval_seconds = 0.05

    # Track which pids we see in this snapshot to evict dead ones later
    seen_pids = set()

    for proc in curr_snapshot:
        pid = proc["pid"]
        seen_pids.add(pid)

        prev = prev_cache.get(pid)

        total_time_now = proc["user_time_100ns"] + proc["kernel_time_100ns"]

        if prev:
            total_time_prev = prev["user_time_100ns"] + prev["kernel_time_100ns"]
            dt_100ns = max(0, total_time_now - total_time_prev)

            # convert 100ns units to seconds
            dt_seconds = dt_100ns / 10_000_000.0

            cpu = (dt_seconds / interval_seconds) * 100 / max(1, cpu_count)
        else:
            cpu = 0.0

        cpu = max(0.0, min(cpu, 100.0))

        results.append({
            "pid": pid,
            "ppid": proc["ppid"],
            "name": proc["name"],
            "threads": proc["threads"],
            "cpu_percent": cpu,
            "rss_bytes": proc["rss_bytes"],
        })

        # Update cache in-place
        prev_cache[pid] = proc

    # Evict dead pids
    # We do this by checking keys in prev_cache that are NOT in seen_pids
    dead_pids = [pid for pid in prev_cache if pid not in seen_pids]
    for pid in dead_pids:
        del prev_cache[pid]

    return results
