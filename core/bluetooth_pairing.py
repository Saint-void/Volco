import subprocess

def enable_bluetooth_pairing():
    """Sets the Pi to headless mode and makes it discoverable."""
    print("📡 [BT MODE] Initializing Bluetooth (No-PIN Mode)...")
    
    try:
        # ⚡ 1. Tell Linux we have no screen or keyboard for PINs
        subprocess.run(["bluetoothctl", "agent", "NoInputNoOutput"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["bluetoothctl", "default-agent"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # ⚡ 2. Turn on the Bluetooth radio
        subprocess.run(["bluetoothctl", "power", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # ⚡ 3. Open the gates for pairing
        subprocess.run(["bluetoothctl", "pairable", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["bluetoothctl", "discoverable", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("✅ [BT MODE] Volco is now visible and will pair without a PIN!")
        
    except Exception as e:
        print(f"⚠️ [BT MODE] Bluetooth initialization failed: {e}")