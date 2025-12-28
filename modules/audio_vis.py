"""
Audio Visualizer module.
Uses WASAPI loopback to capture Windows audio output and perform FFT analysis.
"""

import threading
import time

# Graceful import handling
AUDIO_AVAILABLE = False
try:
    import numpy as np
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    np = None
    sd = None


class AudioVisualizer:
    """
    Captures system audio via WASAPI loopback and provides frequency band magnitudes.
    Thread-safe design for use with the main render loop.
    """
    
    # Frequency band definitions
    BASS_LOW = 60       # Hz
    BASS_HIGH = 120     # Hz
    LOW_MID_LOW = 120   # Hz
    LOW_MID_HIGH = 500  # Hz
    HIGH_MID_LOW = 2000 # Hz
    HIGH_MID_HIGH = 6000 # Hz
    
    def __init__(self, num_cpu_cores=8):
        """Initialize the audio visualizer.
        
        Args:
            num_cpu_cores: Number of CPU cores to generate bands for
        """
        if not AUDIO_AVAILABLE:
            raise RuntimeError("Audio dependencies not available")
        
        self.num_cpu_cores = num_cpu_cores
        self.sample_rate = 44100
        self.block_size = 2048  # FFT size
        
        # Magnitude values (0-100 scale for bar display)
        self._lock = threading.Lock()
        self._ram_magnitude = 0.0       # Bass (60-120 Hz)
        self._swap_magnitude = 0.0      # Low-mid (120-500 Hz)  
        self._disk_magnitude = 0.0      # High-mid (2-6 kHz)
        self._cpu_magnitudes = [0.0] * num_cpu_cores  # Log-spaced bands
        
        # Audio stream
        self._stream = None
        self._running = False
        
        # Pre-compute CPU frequency bands (log-spaced from 200Hz to 16kHz)
        self._cpu_freq_bands = self._compute_cpu_bands()
        
        # Global amplitude multiplier for fine-tuning
        self.amplitude = 2.0
        
        # Smoothing factor (0-1, higher = smoother but less responsive)
        self._smoothing = 0.4
    
    def _compute_cpu_bands(self):
        """Compute log-spaced frequency bands for CPU cores."""
        # Log-space from 200Hz to 16kHz
        min_freq = 200
        max_freq = 16000
        
        # Generate n+1 edges for n bands
        log_min = np.log10(min_freq)
        log_max = np.log10(max_freq)
        edges = np.logspace(log_min, log_max, self.num_cpu_cores + 1)
        
        # Return list of (low, high) tuples
        return [(edges[i], edges[i+1]) for i in range(self.num_cpu_cores)]
    
    def _freq_to_bin(self, freq):
        """Convert frequency to FFT bin index."""
        return int(freq * self.block_size / self.sample_rate)
    
    def _get_band_magnitude(self, fft_magnitudes, low_freq, high_freq):
        """Get average magnitude for a frequency band."""
        low_bin = max(1, self._freq_to_bin(low_freq))
        high_bin = min(len(fft_magnitudes) - 1, self._freq_to_bin(high_freq))
        
        if high_bin <= low_bin:
            return 0.0
        
        # Average magnitude in band
        band = fft_magnitudes[low_bin:high_bin]
        if len(band) == 0:
            return 0.0
        
        return float(np.mean(band))
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Process incoming audio data."""
        if status:
            pass  # Ignore status messages
        
        # Convert to mono if stereo
        if len(indata.shape) > 1:
            audio = np.mean(indata, axis=1)
        else:
            audio = indata.flatten()
        
        # Apply window and compute FFT
        window = np.hanning(len(audio))
        windowed = audio * window
        fft = np.fft.rfft(windowed)
        magnitudes = np.abs(fft)
        
        # Normalize by block size to get approx 0-1 range
        # Increasing the divisor makes it more sensitive (e.g., /12 instead of /4)
        magnitudes = magnitudes / (len(audio) / 12)
        
        # Extract band magnitudes using a custom scaling
        # We don't normalize the whole array anymore, so volume is preserved.
        
        def get_scaled_mag(low, high, boost=1.0):
            val = self._get_band_magnitude(magnitudes, low, high)
            
            # Apply global amplitude and local boost
            val = val * self.amplitude * boost
            
            if val <= 0.0001: 
                return 0.0
            
            # Sharper log curve to boost low-level signals more aggressively
            # val=0.01 -> 0.17
            # val=0.1 -> 0.47
            # val=1.0 -> 1.0
            scaled = np.log10(1 + 39 * val) / np.log10(40)
            
            return min(100.0, scaled * 100.0)

        # Apply mild weighting to balance spectrum (bass is naturally strong)
        ram_mag = get_scaled_mag(self.BASS_LOW, self.BASS_HIGH, boost=0.7) # Bass
        swap_mag = get_scaled_mag(self.LOW_MID_LOW, self.LOW_MID_HIGH, boost=1.0) # Low Mid
        disk_mag = get_scaled_mag(self.HIGH_MID_LOW, self.HIGH_MID_HIGH, boost=1.3) # High Mid
        
        cpu_mags = []
        for i, (low, high) in enumerate(self._cpu_freq_bands):
            # Progressive boost for higher cpu bands
            freq_boost = 1.0 + (i / len(self._cpu_freq_bands)) * 2.5
            mag = get_scaled_mag(low, high, boost=freq_boost)
            cpu_mags.append(mag)
        
        # Apply smoothing and update shared state
        with self._lock:
            self._ram_magnitude = self._smooth(self._ram_magnitude, ram_mag)
            self._swap_magnitude = self._smooth(self._swap_magnitude, swap_mag)
            self._disk_magnitude = self._smooth(self._disk_magnitude, disk_mag)
            
            for i, mag in enumerate(cpu_mags):
                if i < len(self._cpu_magnitudes):
                    self._cpu_magnitudes[i] = self._smooth(self._cpu_magnitudes[i], mag)
    
    def _smooth(self, old_val, new_val):
        """Apply exponential smoothing."""
        return old_val * self._smoothing + new_val * (1 - self._smoothing)
    
    def _find_loopback_device(self):
        """
        Pick the best audio source:
        1. Virtual Output (Voicemeeter B1/B2, VB-Cable) - Direct Capture
        2. System Default Output - WASAPI Loopback
        """
        try:
            devices = sd.query_devices()
            host_apis = sd.query_hostapis()
            
            # Get default output info for fallback matching
            def_out = None
            try:
                idx = sd.default.device[1]
                if idx is not None:
                    def_out = sd.query_devices(idx)
            except: pass
            
            candidates = []
            
            for i, dev in enumerate(devices):
                # Must be WASAPI for compatibility/loopback support
                if 'wasapi' not in host_apis[dev['hostapi']]['name'].lower():
                    continue
                    
                name = dev['name'].lower()
                
                # Priority 0: Known Virtual Outputs (Capture devices)
                # These are "Input" devices in Windows (in_ch > 0) but carry output audio
                if dev['max_input_channels'] > 0:
                    if 'voicemeeter' in name and 'out' in name:
                        # Prioritize B1/Main mix
                        if 'out b1' in name:
                            candidates.append((0, i, False, dev['name']))
                        elif 'out b' in name:
                            candidates.append((1, i, False, dev['name']))
                        else:
                            candidates.append((2, i, False, dev['name']))
                    
                    elif 'virtual cable' in name and 'out' in name:
                        candidates.append((0, i, False, dev['name']))
                
                # Priority 10: System Default Output (Loopback)
                # This ensures we get what the user is actually hearing if they aren't using Voicemeeter capture
                if def_out and dev['max_output_channels'] > 0:
                    # Relaxed name matching to find the WASAPI version of the default output
                    if def_out['name'] in dev['name'] or dev['name'] in def_out['name']:
                        candidates.append((10, i, True, dev['name']))
            
            # Sort by score
            if candidates:
                candidates.sort(key=lambda x: x[0])
                return candidates[0][1], candidates[0][2], candidates[0][3]
                
            # Fallback: If nothing matched, try to force the default output index as a loopback source
            # This is a last resort for systems where name matching fails completely
            if def_out:
                 is_wasapi = 'wasapi' in host_apis[def_out['hostapi']]['name'].lower()
                 return sd.default.device[1], is_wasapi, def_out['name']
                 
            return None, False, None

        except Exception:
            return None, False, None
    
    def start(self):
        """Start audio capture."""
        if self._running:
            return True
        
        device_id, loopback_required, device_name = self._find_loopback_device()
        
        if device_id is None:
            return False

        # Build list of configurations to try
        configs_to_try = []
        
        sample_rates = [48000, 44100, 96000]
        try:
            dev_info = sd.query_devices(device_id)
            default_rate = int(dev_info.get('default_samplerate', 48000))
            if default_rate not in sample_rates:
                sample_rates.insert(0, default_rate)
        except: pass

        for rate in sample_rates:
            # Config 1: Stereo
            configs_to_try.append({
                'device': device_id,
                'samplerate': rate,
                'blocksize': self.block_size,
                'channels': 2,
                'extra_settings': self._get_wasapi_settings(loopback=loopback_required)
            })
            
            # Config 2: Mono (Fallback)
            configs_to_try.append({
                'device': device_id,
                'samplerate': rate,
                'blocksize': self.block_size,
                'channels': 1,
                'extra_settings': self._get_wasapi_settings(loopback=loopback_required)
            })
        
        # CRITICAL: We DO NOT fall back to device=None here.
        # device=None opens the Default Input (Mic), which we strictly want to avoid.
        
        for config in configs_to_try:
            try:
                extra = config.pop('extra_settings')
                actual_rate = config['samplerate']
                if extra:
                    self._stream = sd.InputStream(callback=self._audio_callback, extra_settings=extra, **config)
                else:
                    self._stream = sd.InputStream(callback=self._audio_callback, **config)
                
                self._stream.start()
                self._running = True
                self.sample_rate = actual_rate
                return True
            except Exception:
                continue
        
        return False
    
    def _get_wasapi_settings(self, loopback=False):
        """Get WASAPI settings."""
        try:
            return sd.WasapiSettings(exclusive=False, loopback=loopback)
        except Exception:
            return None
    
    def stop(self):
        """Stop audio capture."""
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        
        # Reset magnitudes
        with self._lock:
            self._ram_magnitude = 0.0
            self._swap_magnitude = 0.0
            self._disk_magnitude = 0.0
            self._cpu_magnitudes = [0.0] * self.num_cpu_cores
    
    def get_magnitudes(self):
        """Get current frequency band magnitudes.
        
        Returns:
            dict with keys: 'ram', 'swap', 'disk', 'cpu' (list)
            All values are 0-100 scale suitable for bar display.
        """
        with self._lock:
            return {
                'ram': self._ram_magnitude,
                'swap': self._swap_magnitude,
                'disk': self._disk_magnitude,
                'cpu': list(self._cpu_magnitudes)
            }
    
    @property
    def is_running(self):
        """Check if audio capture is active."""
        return self._running