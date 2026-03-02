import subprocess
import platform

def enable_bluetooth_pairing():
    """Turns on the Bluetooth chip and makes Volco discoverable to your phone."""
    print("📡 [BT MODE] Initializing Bluetooth...")
    
    if platform.system() == "Windows":
        print("⚠️ [BT MODE] Windows PC detected. Simulating Bluetooth Discoverability.")
        print("✅ [BT MODE] (Pretend your phone just connected to Volco!)")
        return

    # ⚡ This is the actual Raspberry Pi Zero 2W hardware code
    try:
        # 1. Turn the Bluetooth chip on
        subprocess.run(["bluetoothctl", "power", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 2. Allow phones to see Volco
        subprocess.run(["bluetoothctl", "discoverable", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 3. Allow phones to pair without a PIN code
        subprocess.run(["bluetoothctl", "pairable", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("✅ [BT MODE] Volco is now visible on your phone's Bluetooth menu!")
    except Exception as e:
        print(f"❌ [BT MODE] Failed to initialize Bluetooth hardware: {e}")
        