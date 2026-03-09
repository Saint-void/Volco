import subprocess
import time
import threading

# ⚡ VOLCO'S BLUETOOTH MEMORY
_current_device = None

def _monitor_connections():
    """Background loop to ensure only one device is connected at a time."""
    global _current_device
    while True:
        try:
            # Ask Linux for a list of all currently connected devices
            result = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True, check=False)
            lines = result.stdout.strip().split('\n')
            
            # Extract just the MAC addresses (e.g., A1:B2:C3:D4:E5:F6)
            connected_macs = [line.split()[1] for line in lines if line.startswith("Device")]

            if len(connected_macs) == 1:
                # Normal state: exactly one device is connected. Remember it!
                _current_device = connected_macs[0]
            
            elif len(connected_macs) > 1:
                # 🚨 MULTIPLE DEVICES DETECTED!
                for mac in connected_macs:
                    # Find the "new" device that just connected
                    if mac != _current_device and _current_device is not None:
                        print(f"\n🔄 [BT MODE] Device swap! New device connected. Kicking off the old one...")
                        # Drop the old device
                        subprocess.run(["bluetoothctl", "disconnect", _current_device], check=False, stdout=subprocess.DEVNULL)
                        _current_device = mac 
                        break
                else:
                    # Fallback: If both connect at the exact same millisecond, keep the first, drop the rest
                    _current_device = connected_macs[0]
                    for mac in connected_macs[1:]:
                        subprocess.run(["bluetoothctl", "disconnect", mac], check=False, stdout=subprocess.DEVNULL)
        except Exception:
            pass
        
        # Check every 2 seconds (uses virtually 0% CPU)
        time.sleep(2)

def enable_bluetooth_pairing():
    """Turns on the Bluetooth radio and deploys the strict connection bouncer."""
    print("📡 [BT MODE] Waking up Bluetooth radio & deploying connection bouncer...")
    try:
        # Turn the radio on and make it visible
        subprocess.run(["bluetoothctl", "power", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["bluetoothctl", "discoverable", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # ⚡ Spin up the strict "One at a time" enforcer in the background!
        threading.Thread(target=_monitor_connections, daemon=True).start()
        
    except Exception as e:
        print(f"⚠️ [BT MODE] Bluetooth error: {e}")