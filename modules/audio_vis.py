#                                __    __        _____  ___  ___ 
#                               / / /\ \ \/\  /\/__   \/___\/ _ \
#                               \ \/  \/ / /_/ /  / /\//  // /_)/
#                                \  /\  / __  /  / / / \_// ___/ 
#                                 \/  \/\/ /_/   \/  \___/\/     
#                                                                
#            BECUASE ANY GOOD APP NEEDS A EASTER EGG! THIS PROCESSES AUDIO INFO FOR LATER

import threading
import time

# if shit breaks put a logger in here

# look at ln 13

AUDIO_AVAILABLE = False
try:
    import numpy as np
    import sounddevice as sd
    # Try to see if the dll loaded
    _ = sd.query_devices()
    AUDIO_AVAILABLE = True
except Exception:
    # If anything fails (ImportError, OSError for DLLs, etc.), party mode is disabled
    np = None
    sd = None


class AudioVisualizer:
    """
    Captures system audio via WASAPI loopback.
    Includes 'Silence Detection' and 'Gain Boosting'.
    """
    
    # Frequency band definitions
    BASS_LOW = 60
    BASS_HIGH = 120
    LOW_MID_LOW = 120
    LOW_MID_HIGH = 500
    HIGH_MID_LOW = 2000
    HIGH_MID_HIGH = 6000
    
    def __init__(self, num_cpu_cores=8):
        if not AUDIO_AVAILABLE:
            return
        
        self.num_cpu_cores = num_cpu_cores
        self.block_size = 2048
        
        # Thread safety
        self._lock = threading.Lock()
        self._ram_magnitude = 0.0
        self._swap_magnitude = 0.0
        self._disk_magnitude = 0.0
        self._cpu_magnitudes = [0.0] * num_cpu_cores
        
        # Audio internals
        self._stream = None
        self._running = False
        self._cpu_freq_bands = self._compute_cpu_bands()
        
        # Auto-Gain Control (AGC)
        self.base_amplitude = 0.7 # early testing shows this to be *very* sensitive
        self.current_max_peak = 0.01

    def _get_safe_wasapi_settings(self):
        """Attempts to create WASAPI settings without crashing on version mismatches."""
        try:
            # We try passing it as a dict to see if the constructor accepts it
            return sd.WasapiSettings(exclusive=False, loopback=True)
        except (TypeError, Exception) as e:
            # logging.warning(f"WASAPI Loopback flag rejected: {e}")
            return None

    def _compute_cpu_bands(self):
        min_freq = 200
        max_freq = 16000
        log_min = np.log10(min_freq)
        log_max = np.log10(max_freq)
        edges = np.logspace(log_min, log_max, self.num_cpu_cores + 1)
        return [(edges[i], edges[i+1]) for i in range(self.num_cpu_cores)]
    
    def _freq_to_bin(self, freq, sample_rate):
        return int(freq * self.block_size / sample_rate)
    
    def _get_band_magnitude(self, fft_magnitudes, low_freq, high_freq, sample_rate):
        low_bin = max(1, self._freq_to_bin(low_freq, sample_rate))
        high_bin = min(len(fft_magnitudes) - 1, self._freq_to_bin(high_freq, sample_rate))
        
        if high_bin <= low_bin: return 0.0
        
        band = fft_magnitudes[low_bin:high_bin]
        if len(band) == 0: return 0.0
        
        return float(np.mean(band))

    def _audio_callback(self, indata, frames, time_info, status):
            if status:
                return
            
            # 1. Downmix to Mono
            if len(indata.shape) > 1:
                audio = np.mean(indata, axis=1)
            else:
                audio = indata.flatten()
                
            # 2. Check for silence
            peak = np.max(np.abs(audio))
            
            # If it's silent, we DON'T return. We set target values to 0 
            # so the smoothing logic pulls the bars down.
            if peak < 0.0001:
                with self._lock:
                    # Apply a slightly faster decay when truly silent
                    decay = 0.9 
                    self._ram_magnitude *= decay
                    self._swap_magnitude *= decay
                    self._disk_magnitude *= decay
                    for i in range(len(self._cpu_magnitudes)):
                        self._cpu_magnitudes[i] *= decay
                return

            # 3. AGC (Auto Gain Control)
            # This prevents the "sticky" feeling when volume changes drastically
            self.current_max_peak = max(peak, self.current_max_peak * 0.995)
            norm_audio = audio / (self.current_max_peak + 1e-6)

            try:
                # Window & FFT
                window = np.hanning(len(norm_audio))
                windowed = norm_audio * window
                fft = np.fft.rfft(windowed)
                magnitudes = np.abs(fft)
                
                sr = self._stream.samplerate if self._stream else 44100

                def get_val(low, high, mult=1.0):
                    mag = self._get_band_magnitude(magnitudes, low, high, sr)
                    # Visual scaling
                    mag = mag * mult * self.base_amplitude
                    if mag <= 0: return 0.0
                    # Use a steeper log curve to make the bottom end more responsive
                    return min(100.0, np.log10(1 + mag * 10) * 35)

                # Calculate "Target" values
                t_ram = get_val(self.BASS_LOW, self.BASS_HIGH, 1.2)
                t_swap = get_val(self.LOW_MID_LOW, self.LOW_MID_HIGH, 1.0)
                t_disk = get_val(self.HIGH_MID_LOW, self.HIGH_MID_HIGH, 1.0)
                t_cpu = [get_val(l, h, 1.5) for (l, h) in self._cpu_freq_bands]

                # 4. Atomic Update with Smoothing
                # Increased 'new' weight (0.4) to make it feel snappier/less "sticky"
                with self._lock:
                    alpha = 0.4
                    beta = 1.0 - alpha
                    self._ram_magnitude = (t_ram * alpha) + (self._ram_magnitude * beta)
                    self._swap_magnitude = (t_swap * alpha) + (self._swap_magnitude * beta)
                    self._disk_magnitude = (t_disk * alpha) + (self._disk_magnitude * beta)
                    for i in range(min(len(t_cpu), len(self._cpu_magnitudes))):
                        self._cpu_magnitudes[i] = (t_cpu[i] * alpha) + (self._cpu_magnitudes[i] * beta)
                        
            except Exception as e:
                pass

    def _iter_priority_devices(self):
        """
        Yields devices based on 'Expansive' priority:
        1. Voicemeeter Virtual Busses (VAIO, AUX, VAIO3)
        2. Virtual Audio Cables
        3. WASAPI Loopback of the Default Output
        4. Legacy Stereo Mix
        """
        try:
            devices = sd.query_devices()
            host_apis = sd.query_hostapis()
            wasapi_api_idx = next((i for i, h in enumerate(host_apis) if 'wasapi' in h['name'].lower()), -1)
        except Exception as e:
            # logging.error(f"Could not query devices: {e}")
            return

        # PRIORITY 1: Voicemeeter Virtual Busses (B1, B2, AUX)
        # We look for INPUTS (Recording tab) because these are the 'Output' of the mixer
        vm_keywords = ['voicemeeter output', 'voicemeeter aux output', 'vaio3 output', 'b1', 'b2']
        for i, dev in enumerate(devices):
            name = dev['name'].lower()
            if any(k in name for k in vm_keywords) and dev['max_input_channels'] > 0:
                yield (i, False, f"Voicemeeter Bus: {dev['name']}")

        # PRIORITY 2: VB-Cables
        for i, dev in enumerate(devices):
            name = dev['name'].lower()
            if 'virtual cable' in name and dev['max_input_channels'] > 0:
                yield (i, False, f"Virtual Cable: {dev['name']}")

        # PRIORITY 3: WASAPI Loopback (Stock Windows 10/11)
        if wasapi_api_idx != -1:
            try:
                default_out_idx = sd.default.device[1]
                if default_out_idx >= 0:
                    def_name = devices[default_out_idx]['name']
                    for i, dev in enumerate(devices):
                        if dev['hostapi'] == wasapi_api_idx and dev['max_output_channels'] > 0:
                            if def_name in dev['name'] or dev['name'] in def_name:
                                yield (i, True, f"WASAPI Loopback: {dev['name']}")
            except: pass

        # PRIORITY 4: Legacy Stereo Mix
        for i, dev in enumerate(devices):
            name = dev['name'].lower()
            if ('stereo mix' in name or 'what u hear' in name) and dev['max_input_channels'] > 0:
                yield (i, False, f"Legacy Mix: {dev['name']}")

    def start(self):
        if self._running: return True
        # logging.info("--- Starting Audio Capture ---")
        # logging.info("Aw shucks you found the secret! Eh, have fun!")

        for dev_idx, needs_loopback, name in self._iter_priority_devices():
            # logging.info(f"Trying Device: {name}")
            
            try:
                dev_info = sd.query_devices(dev_idx)
                samplerate = int(dev_info['default_samplerate'])
                
                extra = self._get_safe_wasapi_settings() if needs_loopback else None
                
                # If we need loopback but the library rejected the flag, 
                # this device will likely be silent. Skip it.
                if needs_loopback and extra is None:
                    # logging.warning(f"Skipping {name} - Loopback flag required but unsupported.")
                    continue

                self._stream = sd.InputStream(
                    device=dev_idx,
                    channels=min(dev_info['max_input_channels'], 2) if not needs_loopback else 2,
                    samplerate=samplerate,
                    callback=self._audio_callback,
                    blocksize=self.block_size,
                    extra_settings=extra
                )
                self._stream.start()
                self._running = True
                # logging.info(f"Successfully locked onto: {name}")
                return True
            except Exception as e:
                # logging.error(f"Failed to open {name}: {e}")
                continue
        
        return False

    def stop(self):
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception: pass
            self._stream = None

    def get_magnitudes(self):
        with self._lock:
            return {
                'ram': self._ram_magnitude,
                'swap': self._swap_magnitude,
                'disk': self._disk_magnitude,
                'cpu': list(self._cpu_magnitudes)
            }

    @property
    def is_running(self):
        return self._running