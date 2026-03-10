import subprocess
import time
import threading

def _bluetooth_background_manager():
    """Handles 100% automated passkey bypassing, force-trusting, and device locking."""
    locked_device = None
    
    # ⚡ 1. THE GHOST TERMINAL
    # We open bluetoothctl in the background and permanently lock it into "Dumb Headset" mode
    bt_proc = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    bt_proc.stdin.write("power on\n")
    bt_proc.stdin.write("agent NoInputNoOutput\n") # Bypasses the PIN code
    bt_proc.stdin.write("default-agent\n")
    bt_proc.stdin.write("discoverable on\n")
    bt_proc.stdin.write("pairable on\n")
    bt_proc.stdin.flush()

    while True:
        try:
            # ⚡ 2. THE AUTO-TRUST BOMB
            # We grab every device the Pi has ever seen and aggressively force-trust it.
            # This completely bypasses the "Authorize service (yes/no)" prompt!
            devices_out = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True).stdout
            macs = [line.split()[1] for line in devices_out.strip().split('\n') if line.startswith("Device")]
            
            for mac in macs:
                subprocess.run(["bluetoothctl", "trust", mac], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # ⚡ 3. THE VAULT DOOR
            # Strict "First Come, First Served" connection lock
            connected_out = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True).stdout
            connected_macs = [line.split()[1] for line in connected_out.strip().split('\n') if line.startswith("Device")]

            if len(connected_macs) == 0:
                if locked_device is not None:
                    print("\n🔓 [BT MODE] Device disconnected. Volco is free.")
                    locked_device = None
            
            elif len(connected_macs) == 1:
                if locked_device is None:
                    locked_device = connected_macs[0]
                    print(f"\n🔒 [BT MODE] Locked to device: {locked_device}")
            
            elif len(connected_macs) > 1:
                for mac in connected_macs:
                    if mac != locked_device:
                        print(f"\n🛡️ [BT MODE] Intruder blocked! Kicking MAC: {mac}")
                        subprocess.run(["bluetoothctl", "disconnect", mac], stdout=subprocess.DEVNULL)
        except Exception:
            pass
        
        # We loop every 1 second to catch the MAC address and Trust it BEFORE Linux can prompt you!
        time.sleep(1)

def enable_bluetooth_pairing():
    """Wakes up the Volco hardware and deploys the Zero-Touch security manager."""
    print("📡 [BT MODE] Deploying Zero-Touch Passkey Bypass & Vault...")
    threading.Thread(target=_bluetooth_background_manager, daemon=True).start()