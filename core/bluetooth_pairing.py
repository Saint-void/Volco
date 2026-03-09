import subprocess
import time
import threading

# ⚡ VOLCO'S BLUETOOTH LOCK
_locked_device = None

def _monitor_connections():
    """Locks Volco to the FIRST device that connects and kicks intruders away."""
    global _locked_device
    while True:
        try:
            # Ask Linux for a list of all currently connected devices
            result = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True, check=False)
            lines = result.stdout.strip().split('\n')
            
            # Extract just the MAC addresses
            connected_macs = [line.split()[1] for line in lines if line.startswith("Device")]

            if len(connected_macs) == 0:
                # Nobody is connected. Open the gates!
                if _locked_device is not None:
                    print("\n🔓 [BT MODE] Device disconnected. Volco is free for a new connection.")
                    _locked_device = None
            
            elif len(connected_macs) == 1:
                # One device is connected. Lock it in!
                if _locked_device is None:
                    _locked_device = connected_macs[0]
                    print(f"\n🔒 [BT MODE] Locked to device: {_locked_device}. Rejecting all others.")
            
            elif len(connected_macs) > 1:
                # 🚨 INTRUDER ALERT! Someone else is trying to connect.
                for mac in connected_macs:
                    if mac != _locked_device:
                        print(f"\n🛡️ [BT MODE] Intruder blocked! Kicking MAC: {mac}")
                        # Immediately boot the new device trying to sneak in
                        subprocess.run(["bluetoothctl", "disconnect", mac], check=False, stdout=subprocess.DEVNULL)
        except Exception:
            pass
        
        # Check every 2 seconds
        time.sleep(2)

def enable_bluetooth_pairing():
    """Turns on the Bluetooth radio and deploys the security lock."""
    print("📡 [BT MODE] Waking up Bluetooth radio & deploying the security vault...")
    try:
        # Turn the radio on and make it visible
        subprocess.run(["bluetoothctl", "power", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["bluetoothctl", "discoverable", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # ⚡ Spin up the strict "First Come, First Served" lock in the background!
        threading.Thread(target=_monitor_connections, daemon=True).start()
        
    except Exception as e:
        print(f"⚠️ [BT MODE] Bluetooth error: {e}")