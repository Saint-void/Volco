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
            # Added timeout=5 to prevent the background thread from hanging
            result = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True, check=False, timeout=5)
            lines = result.stdout.strip().split('\n')
            
            connected_macs = [line.split()[1] for line in lines if line.startswith("Device")]

            if len(connected_macs) == 0:
                if _locked_device is not None:
                    print("\n🔓 [BT MODE] Device disconnected. Volco is free for a new connection.")
                    _locked_device = None
            
            elif len(connected_macs) == 1:
                if _locked_device is None:
                    _locked_device = connected_macs[0]
                    print(f"\n🔒 [BT MODE] Locked to device: {_locked_device}. Rejecting all others.")
            
            elif len(connected_macs) > 1:
                for mac in connected_macs:
                    if mac != _locked_device:
                        print(f"\n🛡️ [BT MODE] Intruder blocked! Kicking MAC: {mac}")
                        subprocess.run(["bluetoothctl", "disconnect", mac], check=False, stdout=subprocess.DEVNULL, timeout=3)
        except Exception:
            pass
        
        time.sleep(2)

def enable_bluetooth_pairing():
    """Turns on the Bluetooth radio and deploys the security vault."""
    print("📡 [BT MODE] Waking up Bluetooth radio & deploying the security vault...")
    try:
        # ⚡ THE FIX: Added timeout=3 so it physically cannot freeze forever!
        subprocess.run(["bluetoothctl", "power", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        subprocess.run(["bluetoothctl", "discoverable", "on"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        
        threading.Thread(target=_monitor_connections, daemon=True).start()
        print("✅ [BT MODE] Bluetooth radio awake and Vault active.")
        
    except subprocess.TimeoutExpired:
        print("\n⚠️ [CRITICAL] The Linux Bluetooth system is frozen and not responding!")
    except Exception as e:
        print(f"⚠️ [BT MODE] Bluetooth error: {e}")