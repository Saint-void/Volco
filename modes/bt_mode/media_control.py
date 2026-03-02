import time
import platform
import ctypes

def toggle_media():
    """Bypasses high-level libraries and sends raw OS hardware codes."""
    if platform.system() == "Windows":
        # 0xB3 is the exact Virtual Key Code for the hardware Play/Pause button
        VK_MEDIA_PLAY_PAUSE = 0xB3
        
        # Press the key down
        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
        # Release the key
        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 2, 0)
    else:
        # We will leave this here for when Void Enterprises moves to Raspberry Pi (Linux)
        import subprocess
        try:
            subprocess.run(["playerctl", "play-pause"], check=False)
        except Exception:
            pass

def pause_media():
    """Simulates pressing the physical Pause button on a headset."""
    print("⏸️  [BT MODE] Sending OS hardware pause command...")
    toggle_media()
    
    # Give the OS half a second to fade the music out before the AI beep
    time.sleep(0.5) 

def resume_media():
    """Simulates pressing the physical Play button to resume music."""
    print("▶️  [BT MODE] Sending OS hardware play command...")
    toggle_media()
    time.sleep(0.5)