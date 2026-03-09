import subprocess

def enable_bluetooth_pairing():
    """Turns on the Bluetooth radio so trusted devices can auto-connect."""
    print("📡 [BT MODE] Waking up Bluetooth radio...")
    try:
        subprocess.run(["bluetoothctl", "power", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["bluetoothctl", "discoverable", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"⚠️ [BT MODE] Bluetooth error: {e}") 