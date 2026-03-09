import subprocess
import time

def enable_bluetooth_pairing():
    """Sets the Pi to headless mode and makes it discoverable."""
    print("📡 [BT MODE] Initializing Permanent Headless Bluetooth...")
    
    try:
        # ⚡ 1. The Background Guardian
        # Popen keeps the agent alive in the background to auto-approve PINs
        subprocess.Popen(["bt-agent", "-c", "NoInputNoOutput"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        time.sleep(1) # Give the agent a second to wake up
        
        # ⚡ 2. Turn on the radio
        subprocess.run(["bluetoothctl", "power", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # ⚡ 3. Open the gates for pairing
        subprocess.run(["bluetoothctl", "pairable", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["bluetoothctl", "discoverable", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("✅ [BT MODE] Volco is visible and the PIN-bypass agent is locked in!")
        
    except Exception as e:
        print(f"⚠️ [BT MODE] Bluetooth initialization failed: {e}")