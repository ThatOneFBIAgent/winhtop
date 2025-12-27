"""
Audio Visualizer module for Party Mode easter egg.
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
        
        # Smoothing factor (0-1, higher = smoother but less responsive)
        self._smoothing = 0.3
    
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
        
        # Normalize (with some headroom to prevent clipping)
        max_mag = np.max(magnitudes)
        if max_mag > 0:
            magnitudes = magnitudes / max_mag
        
        # Extract band magnitudes
        ram_mag = self._get_band_magnitude(magnitudes, self.BASS_LOW, self.BASS_HIGH) * 100
        swap_mag = self._get_band_magnitude(magnitudes, self.LOW_MID_LOW, self.LOW_MID_HIGH) * 100
        disk_mag = self._get_band_magnitude(magnitudes, self.HIGH_MID_LOW, self.HIGH_MID_HIGH) * 100
        
        cpu_mags = []
        for low, high in self._cpu_freq_bands:
            mag = self._get_band_magnitude(magnitudes, low, high) * 100
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
        """Pick the best available loopback / virtual output device.
        
        Priority order:
        1. Voicemeeter B1 virtual output bus (captures all audio sent to B1)
        2. Voicemeeter B2/B3 buses
        3. Voicemeeter Input / AUX Input (capture what's being sent to VM)
        4. Stereo Mix / Loopback (Windows default capture)
        5. Any other WASAPI input
        """
        try:
            devices = sd.query_devices()
            candidates = []

            for i, dev in enumerate(devices):
                if dev['max_input_channels'] <= 0:
                    continue

                name = dev['name'].lower()
                api = sd.query_hostapis(dev['hostapi'])['name'].lower()

                # Only prioritize WASAPI devices (best quality on Windows)
                if 'wasapi' not in api:
                    # WDM/DirectSound fallback - low priority
                    if 'wdm' in api or 'directsound' in api:
                        if 'voicemeeter' in name or 'stereo mix' in name:
                            candidates.append((100, i, dev))
                    continue

                # ---- Voicemeeter B buses (virtual outputs) ----
                # These capture mixed audio output, B1 is typically the main bus
                if 'voicemeeter' in name and 'out' in name:
                    if 'out b1' in name or ('out b' not in name and 'out a' not in name and 'aux' not in name and 'vaio3' not in name):
                        # B1 is highest priority (or generic "Voicemeeter Out" which is B1)
                        candidates.append((0, i, dev))
                    elif 'out b2' in name:
                        candidates.append((1, i, dev))
                    elif 'out b3' in name:
                        candidates.append((2, i, dev))
                    # Skip A buses (hardware out, not what we want)
                    continue

                # ---- Voicemeeter Inputs (capture what's sent to VM) ----
                if 'voicemeeter' in name and ('input' in name or 'aux' in name):
                    if 'aux' in name:
                        candidates.append((3, i, dev))  # AUX input
                    else:
                        candidates.append((4, i, dev))  # Main input
                    continue

                # ---- Stereo Mix / Loopback (good generic source) ----
                if 'loopback' in name or 'stereo mix' in name or 'what u hear' in name:
                    candidates.append((5, i, dev))
                    continue

                # ---- Other WASAPI inputs (last resort) ----
                candidates.append((50, i, dev))

            if not candidates:
                return None

            # Pick lowest priority value (highest priority device)
            candidates.sort(key=lambda x: x[0])
            _, index, dev = candidates[0]
            return index

        except Exception:
            return None
    
    def start(self):
        """Start audio capture."""
        if self._running:
            return True
        
        device_id = self._find_loopback_device()
        
        # Common sample rates to try (in order of preference)
        # Start with device default, then try common rates
        sample_rates_to_try = [48000, 44100, 96000]
        
        # Get device's default sample rate and put it first
        if device_id is not None:
            try:
                dev_info = sd.query_devices(device_id)
                default_rate = int(dev_info.get('default_samplerate', 48000))
                if default_rate not in sample_rates_to_try:
                    sample_rates_to_try.insert(0, default_rate)
                else:
                    # Move default to front
                    sample_rates_to_try.remove(default_rate)
                    sample_rates_to_try.insert(0, default_rate)
            except Exception:
                pass
        
        # Build list of configurations to try
        configs_to_try = []
        
        if device_id is not None:
            for sample_rate in sample_rates_to_try:
                # Try with WASAPI settings, 2 channels
                configs_to_try.append({
                    'device': device_id,
                    'samplerate': sample_rate,
                    'blocksize': self.block_size,
                    'channels': 2,
                    'extra_settings': self._get_wasapi_settings()
                })
                # Try without WASAPI settings, 2 channels
                configs_to_try.append({
                    'device': device_id,
                    'samplerate': sample_rate,
                    'blocksize': self.block_size,
                    'channels': 2,
                    'extra_settings': None
                })
                # Try with 1 channel
                configs_to_try.append({
                    'device': device_id,
                    'samplerate': sample_rate,
                    'blocksize': self.block_size,
                    'channels': 1,
                    'extra_settings': None
                })
        
        # Also try default device as last fallback
        for sample_rate in sample_rates_to_try:
            configs_to_try.append({
                'device': None,
                'samplerate': sample_rate,
                'blocksize': self.block_size,
                'channels': 1,
                'extra_settings': None
            })
        
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
                self.sample_rate = actual_rate  # Update for FFT calculations
                return True
            except Exception:
                continue
        
        return False
    
    def _get_wasapi_settings(self):
        """Get WASAPI settings if available."""
        try:
            return sd.WasapiSettings(exclusive=False)
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

# TODO: make this audio amplitude sensitive (ergo the audio in being louder should make the bars taller)