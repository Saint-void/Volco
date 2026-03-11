import subprocess
import time
import threading

def _bluetooth_background_manager():
    """Handles bulletproof NoInputNoOutput agent, auto-trusting, and device lock."""
    locked_device = None

    # ⚡ 1. CLEAN THE SLATE
    # Kill any frozen Bluetooth processes from previous crashes
    subprocess.run(["sudo", "killall", "bluetoothctl", "bt-agent"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    time.sleep(1)

    # ⚡ 2. THE OFFICIAL HEADLESS AGENT
    # Instead of typing text, we launch the actual headless agent tool as a background process!
    print("🛡️ [BT MODE] Launching Official NoInputNoOutput Agent...")
    agent_proc = subprocess.Popen(["bt-agent", "-c", "NoInputNoOutput"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1) # Give the agent a second to boot up

    # ⚡ 3. WAKE UP THE RADIO
    subprocess.run(["bluetoothctl", "power", "on"], stdout=subprocess.DEVNULL)
    subprocess.run(["bluetoothctl", "discoverable", "on"], stdout=subprocess.DEVNULL)
    subprocess.run(["bluetoothctl", "pairable", "on"], stdout=subprocess.DEVNULL)

    while True:
        try:
            # Keep the beacon alive
            subprocess.run(["bluetoothctl", "discoverable", "on"], stdout=subprocess.DEVNULL)
            subprocess.run(["bluetoothctl", "pairable", "on"], stdout=subprocess.DEVNULL)

            # ⚡ 4. AUTO-TRUST LOOP
            devices_out = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True).stdout
            macs = [line.split()[1] for line in devices_out.strip().split('\n') if line.startswith("Device")]
            for mac in macs:
                subprocess.run(["bluetoothctl", "trust", mac], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # ⚡ 5. THE VAULT DOOR
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
        
        time.sleep(1)

def enable_bluetooth_pairing():
    """Starts the automated Bluetooth manager."""
    print("📡 [BT MODE] Deploying Zero-Touch Bluetooth Manager...")
    threading.Thread(target=_bluetooth_background_manager, daemon=True).start()