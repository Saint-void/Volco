import subprocess
import platform
import time
from core.audio_io import play_sfx

def enable_bluetooth_pairing():
    """Turns on the Bluetooth chip and makes Volco discoverable to your phone."""
    print("📡 [BT MODE] Initializing Bluetooth...")
    
    # ⚡ VUI 3: The Pairing Announcement
    play_sfx("./assets/sounds/bt_pairing.wav", async_play=True)
    
    if platform.system() == "Windows":
        print("⚠️ [BT MODE] Windows PC detected. Simulating Bluetooth Discoverability.")
        return

    # Raspberry Pi Zero 2W Hardware Code
    try:
        subprocess.run(["bluetoothctl", "power", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["bluetoothctl", "discoverable", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["bluetoothctl", "pairable", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("✅ [BT MODE] Volco is now visible on your phone's Bluetooth menu!")
    except Exception as e:
        print(f"❌ [BT MODE] Failed to initialize Bluetooth hardware: {e}")