import subprocess
import time
import threading

_locked_device = None

def _monitor_connections():
    """Vault Door: Locks Volco to the FIRST device that connects."""
    global _locked_device
    while True:
        try:
            result = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True, check=False, timeout=5)
            lines = result.stdout.strip().split('\n')
            connected_macs = [line.split()[1] for line in lines if line.startswith("Device")]

            if len(connected_macs) == 0:
                if _locked_device is not None:
                    print("\n🔓 [BT MODE] Device disconnected. Volco is free.")
                    _locked_device = None
            
            elif len(connected_macs) == 1:
                if _locked_device is None:
                    _locked_device = connected_macs[0]
                    print(f"\n🔒 [BT MODE] Locked to device: {_locked_device}")
            
            elif len(connected_macs) > 1:
                for mac in connected_macs:
                    if mac != _locked_device:
                        print(f"\n🛡️ [BT MODE] Intruder blocked! Kicking MAC: {mac}")
                        subprocess.run(["bluetoothctl", "disconnect", mac], check=False, stdout=subprocess.DEVNULL, timeout=3)
        except Exception:
            pass
        time.sleep(2)

def enable_bluetooth_pairing():
    """Brute-forces the headless agent directly into bluetoothctl."""
    print("📡 [BT MODE] Injecting manual NoInputNoOutput commands...")
    
    # ⚡ THE BRUTE FORCE INJECTION
    bash_script = """
    bluetoothctl power on
    bluetoothctl <<EOF
    agent NoInputNoOutput
    default-agent
    discoverable on
    pairable on
    EOF
    """
    
    try:
        # Run the bash injection
        subprocess.run(bash_script, shell=True, executable='/bin/bash', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Start the vault door
        threading.Thread(target=_monitor_connections, daemon=True).start()
        print("✅ [BT MODE] Headless Agent injected and Vault active.")
        
    except Exception as e:
        print(f"⚠️ [BT MODE] Bluetooth error: {e}")