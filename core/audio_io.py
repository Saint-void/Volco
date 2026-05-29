import os
import sys
import time
import audioop
import pyaudio
import platform
import subprocess
from config.config_manager import config

def play_sfx(filename, async_play=False):
    """Plays a sound using OS-level mixers to prevent PyAudio lockups."""
    if not os.path.exists(filename): 
        print(f"⚠️ Missing sound file: {filename}")
        return
        
    try:
        if platform.system() == "Windows":
            import winsound
            flags = winsound.SND_FILENAME   
            if async_play:
                flags |= winsound.SND_ASYNC  # Plays in background
            
            # ⚡ Prevents the default Windows error 'Ding'
            flags |= winsound.SND_NODEFAULT 
            
            winsound.PlaySound(filename, flags)
        else:
            # Future-proofed for your Raspberry Pi (Linux)
            if async_play:
                subprocess.Popen(["aplay", "-q", filename], stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["aplay", "-q", filename], stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"⚠️ SFX Error: {e}")

def print_audio_meter(volume, threshold, is_active, status_text="LISTENING"):
    """Displays the live visual audio meter in the terminal."""
    scaled_vol = int(volume / 400) 
    if scaled_vol > 20: scaled_vol = 20
    bar = "█" * scaled_vol + "-" * (20 - scaled_vol)
    color = "\033[92m" if is_active else "\033[90m"
    reset = "\033[0m"
    sys.stdout.write(f"\r{color}🎤 {status_text} | Level: {volume:05d} | Trig: {threshold} | [{bar}]{reset}")
    sys.stdout.flush()

class AdaptiveNoiseManager:
    def __init__(self, initial_noise_floor=200, alpha=0.02):
        """
        alpha: Smoothing factor (0 to 1). 
               Higher = adapts faster (risky), Lower = more stable.
        """
        self.noise_floor = initial_noise_floor
        self.alpha = alpha
        self.safety_margin = config["audio"].get("safety_margin", 100)

    def update(self, current_level):
        """Updates the noise floor if the current level looks like background noise."""
        # Only update if the sound is 'relatively' quiet (not a sudden shout)
        if current_level < self.noise_floor * 2.0:
            self.noise_floor = (1 - self.alpha) * self.noise_floor + self.alpha * current_level
        return self.get_threshold()

    def get_threshold(self):
        return int(self.noise_floor + self.safety_margin)

def calibrate_mic(duration=1.0):
    """Measures room noise and returns the baseline noise floor using smart averaging."""
    
    # ⚡ FIX 1: Give the system 1.5 seconds to finish playing any boot/connection sounds
    if duration > 0.6: 
        time.sleep(1.5)
        print("\n🤫 Measuring room noise...")
        
    chunk = config["audio"]["chunk"]
    p = pyaudio.PyAudio()
    
    stream = p.open(
        format=pyaudio.paInt16, 
        channels=config["audio"]["channels"], 
        rate=config["audio"]["rate"], 
        input=True, 
        frames_per_buffer=chunk
    )
    
    volumes = []
    start = time.time()
    
    while time.time() - start < duration:
        data = stream.read(chunk, exception_on_overflow=False)
        level = audioop.rms(data, 2)
        volumes.append(level)
            
        if duration > 0.6: 
            print_audio_meter(level, 0, False, "CALIBRATING")
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # ⚡ FIX 2: Sort the volumes and throw away the top 20% (removes sudden spikes/pops)
    # Then take the average of what is left to get the TRUE room baseline.
    volumes.sort()
    valid_volumes = volumes[:int(len(volumes) * 0.8)] 
    
    if not valid_volumes:
        noise_floor = 100 # Fallback 
    else:
        noise_floor = int(sum(valid_volumes) / len(valid_volumes))
        
    # Ensure it never drops below a safe hardware baseline
    noise_floor = max(noise_floor, 100)
        
    safety_margin = config["audio"]["safety_margin"]
    if duration > 0.6: 
        print(f"\n✅ Noise Floor: {noise_floor} | Trig: {noise_floor + safety_margin}\n")
        
    return noise_floor
