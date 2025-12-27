
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
    from modules.ui import render
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
    
    # Fetch hardware info once
    get_hardware_info()
    
    # Prime CPU measurements
    psutil.cpu_percent(percpu=True)
    for proc in psutil.process_iter():
        try:
            proc.cpu_times()
        except:
            pass
    
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
