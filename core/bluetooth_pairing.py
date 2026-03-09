import subprocess
import time

def enable_bluetooth_pairing():
    """Acts like a physical pairing button, making Volco visible to new devices."""
    print("📡 [BT MODE] Entering Pairing Mode (Visible for 60 seconds)...")
    try:
        # Turn the radio on
        subprocess.run(["bluetoothctl", "power", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Make it pairable and visible to phones
        subprocess.run(["bluetoothctl", "pairable", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["bluetoothctl", "discoverable", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("✅ [BT MODE] Volco is ready to pair with new devices!")
        
    except Exception as e:
        print(f"⚠️ [BT MODE] Bluetooth error: {e}")