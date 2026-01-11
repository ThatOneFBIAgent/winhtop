
#                                __    __        _____  ___  ___ 
#                               / / /\ \ \/\  /\/__   \/___\/ _ \
#                               \ \/  \/ / /_/ /  / /\//  // /_)/
#                                \  /\  / __  /  / / / \_// ___/ 
#                                 \/  \/\/ /_/   \/  \___/\/     
#                                                                
#                               
import sys
import os
import time
import psutil

# Check for Windows
if sys.platform != 'win32':
    print("This application is designed for Windows only. If this is linux, use htop instead, and if this is macos, use Activity Monitor.")
    sys.exit(1)

# Import modules
try:
    from modules.config import *
    from modules.state import state
    from modules.utils import *
    from modules.hardware import get_hardware_info, update_system_stats, update_system_stats_fast, update_system_stats_slow
    from modules.processes import get_processes
    from modules.ui import render, render_startup
    from modules.input import handle_input 
except ImportError as e:
    print(f"Error loading modules: {e}")
    time.sleep(2)
    print("Please open an issue on GitHub with the error message (preferably as a .txt file).")
    time.sleep(2)
    sys.exit(1)

try:
    import modules.audio_vis
except ImportError:
    pass

def main():
    """Main application loop."""
    # Enable ANSI
    os.system("")
    
    # Clear screen and hide cursor
    sys.stdout.write("\033[2J\033[?25l")
    sys.stdout.flush()
    
    # Total initialization steps for progress tracking
    TOTAL_STEPS = 100
    current_step = 0
    
    # Helper to advance progress
    def bump_progress(amount=1, msg=None):
        nonlocal current_step
        current_step += amount
        if current_step > TOTAL_STEPS: current_step = TOTAL_STEPS
        render_startup(current_step, TOTAL_STEPS, msg)

    # Step: Initial splash
    bump_progress(5, "Initializing terminal magic...")
    
    # Step: Poke kernel (enable virtual terminal)
    bump_progress(5, "Poking the system kernel...")
    time.sleep(0.1)
    
    # Step: Fetch CPU info (Can take 1-2s)
    bump_progress(5, "Interrogating your CPU...")
    get_hardware_info() 
    
    # Step: GPU & More
    bump_progress(10, "Waking up the GPU...")
    time.sleep(0.05)
    
    # Step: Collect process breadcrumbs
    bump_progress(5, "Collecting process breadcrumbs...")
    psutil.cpu_percent(percpu=True)
    
    # Step: Prime individual process CPU times (Main delay)
    bump_progress(5, "Priming the performance counters...")
    
    # We will use about 50 steps for this loop
    proc_list = list(psutil.process_iter()) # Snapshot first
    total_procs = len(proc_list)
    
    # Flavor text for the loop
    flavor_msgs = [
        "Reordering electrons...",
        "Compiling bitstreams...",
        "Calibrating flux capacitor...",
        "Reticulating splines...",
        "Defragmenting ghosts...",
        "Scanning quantum fluctuations..."
    ]
    
    import random
    
    for i, proc in enumerate(proc_list):
        try:
            proc.cpu_times()
        except:
            pass
            
        # Update UI every chunk of processes
        if i % 10 == 0 or i == total_procs - 1:
            # Calculate progress within the loop (allocating 50 steps)
            loop_progress = int((i / total_procs) * 50)
            base_progress = 35 # Steps before this loop
            
            # Switch flavor text occasionally
            flavor = "Priming performance counters..."
            if i % 40 == 0:
                 flavor = flavor_msgs[(i // 40) % len(flavor_msgs)]
                 
            render_startup(base_progress + loop_progress, TOTAL_STEPS, f"{flavor} ({int(i/total_procs*100)}%)")
            
    current_step = 85 # Jump to after loop
    
    # Step: Initial system stats
    bump_progress(5, "Gathering system vitals...")
    update_system_stats()
    
    # Step: Final polish
    bump_progress(5, "Polishing the UI...")
    get_processes()
    
    # Step: Ready
    bump_progress(5, "Ready to go!")
    time.sleep(0.3)
    
    try:
        last_update = 0
        last_process_update = 0
        frame_count = 0
        
        while state.app_running:
            now = time.time()
            refresh_interval = REFRESH_RATES.get(state.current_refresh_rate, 2.0)
            
            # Party mode: skip ALL psutil updates - bars are driven by audio only
            if state.party_mode:
                # Just render the audio visualization at max speed
                render()
                handle_input()
                time.sleep(max(0.001, refresh_interval * 0.5))
                continue
            
            # For high-speed modes (ultrafast), split updates:
            # - Fast (CPU only): every frame for smooth bars
            # - Slow (mem, disk, net, gpu): every 0.5s
            # - Processes: every 0.5s
            is_high_speed = refresh_interval < 0.5
            slow_update_interval = 0.5 if is_high_speed else refresh_interval
            
            # Always update at refresh interval
            if now - last_update >= refresh_interval:
                if is_high_speed:
                    # High-speed: only CPU stats every frame
                    update_system_stats_fast()
                else:
                    # Normal: all stats every frame
                    update_system_stats()
                frame_count += 1
                last_update = now
            
            # Slow updates (processes + non-CPU stats) less frequently
            if now - last_process_update >= slow_update_interval:
                if is_high_speed:
                    update_system_stats_slow()
                get_processes()
                last_process_update = now
            
            render()
            
            # Input polling - minimal delay for high-speed modes
            if is_high_speed:
                # Quick input check, no long polling loop
                handle_input()
                time.sleep(max(0.001, refresh_interval * 0.5))
            else:
                # Normal polling for slower modes
                poll_end = time.time() + min(0.1, refresh_interval * 0.5)
                while time.time() < poll_end:
                    handle_input()
                    if not state.app_running:
                        break
                    time.sleep(0.02)
                
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # Emergency exit to see errors
        sys.stdout.write("\033[?25h")
        sys.stdout.write(C_RESET)
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up party mode audio if active
        if state.party_visualizer:
            state.party_visualizer.stop()
        
        sys.stdout.write("\033[?25h")  # Show cursor
        sys.stdout.write(C_RESET)
        sys.stdout.write("\033[2J\033[H")
        print("Exiting Task Manager... Cya!")
        time.sleep(1)

if __name__ == "__main__":
    main()
