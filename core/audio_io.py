import os
import sys
import time
import struct
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

def calibrate_mic(duration=1.0):
    """Measures room noise and returns the baseline noise floor."""
    chunk = config["audio"]["chunk"]
    p = pyaudio.PyAudio()
    
    stream = p.open(
        format=pyaudio.paInt16, 
        channels=config["audio"]["channels"], 
        rate=config["audio"]["rate"], 
        input=True, 
        frames_per_buffer=chunk
    )
    
    if duration > 0.6: 
        print("\n🤫 Measuring room noise...")
    
    max_noise = 0
    start = time.time()
    
    while time.time() - start < duration:
        data = stream.read(chunk, exception_on_overflow=False)
        peak = max(struct.unpack_from("%dh" % chunk, data))
        if peak > max_noise: 
            max_noise = peak
            
        if duration > 0.6: 
            print_audio_meter(peak, 0, False, "CALIBRATING")
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    if max_noise < 100: 
        max_noise = 100
        
    safety_margin = config["audio"]["safety_margin"]
    if duration > 0.6: 
        print(f"\n✅ Noise Floor: {max_noise} | Trig: {max_noise + safety_margin}\n")
        
    return max_noise