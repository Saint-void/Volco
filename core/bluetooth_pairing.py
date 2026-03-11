import subprocess
import time
import threading

def _bluetooth_background_manager():
    """Handles bulletproof NoInputNoOutput agent and smart DBus state management."""
    locked_device = None

    # ⚡ 1. CLEAN THE SLATE
    subprocess.run(["sudo", "killall", "bluetoothctl", "bt-agent"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    time.sleep(1)

    # ⚡ 2. START THE AGENT
    print("🛡️ [BT MODE] Launching Official NoInputNoOutput Agent...")
    agent_proc = subprocess.Popen(["bt-agent", "-c", "NoInputNoOutput"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # ⚡ 3. INITIAL WAKE UP
    subprocess.run(["bluetoothctl", "power", "on"], stdout=subprocess.DEVNULL)
    subprocess.run(["bluetoothctl", "discoverable", "on"], stdout=subprocess.DEVNULL)
    subprocess.run(["bluetoothctl", "pairable", "on"], stdout=subprocess.DEVNULL)

    while True:
        try:
            # ⚡ 4. AGENT REVIVAL (If DBus crashes the agent, restart it instantly)
            if agent_proc.poll() is not None:
                print("⚠️ [BT MODE] Agent crashed! Restarting...")
                agent_proc = subprocess.Popen(["bt-agent", "-c", "NoInputNoOutput"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # ⚡ 5. THE VAULT DOOR (Check who is connected)
            connected_out = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True).stdout
            connected_macs = [line.split()[1] for line in connected_out.strip().split('\n') if line.startswith("Device")]

            # SCENARIO A: Nobody is connected
            if len(connected_macs) == 0:
                if locked_device is not None:
                    print("\n🔓 [BT MODE] Device disconnected. Volco is free.")
                    locked_device = None
                    # ONLY turn discoverable back on when a device leaves! (No DBus spam)
                    subprocess.run(["bluetoothctl", "discoverable", "on"], stdout=subprocess.DEVNULL)
                    subprocess.run(["bluetoothctl", "pairable", "on"], stdout=subprocess.DEVNULL)

            # SCENARIO B: Exactly one device is connected
            elif len(connected_macs) == 1:
                if locked_device is None:
                    locked_device = connected_macs[0]
                    print(f"\n🔒 [BT MODE] Locked to device: {locked_device}")
                    
                    # Trust the device so it can auto-reconnect later
                    subprocess.run(["bluetoothctl", "trust", locked_device], stdout=subprocess.DEVNULL)
                    
                    # Turn off discoverability so intruders can't even see Volco on their phones
                    subprocess.run(["bluetoothctl", "discoverable", "off"], stdout=subprocess.DEVNULL)

            # SCENARIO C: Intruder tries to force a connection
            elif len(connected_macs) > 1:
                for mac in connected_macs:
                    if mac != locked_device:
                        print(f"\n🛡️ [BT MODE] Intruder blocked! Kicking MAC: {mac}")
                        subprocess.run(["bluetoothctl", "disconnect", mac], stdout=subprocess.DEVNULL)

        except Exception:
            pass
        
        # Relax the loop to let the CPU breathe
        time.sleep(2)

def enable_bluetooth_pairing():
    """Starts the automated Bluetooth manager."""
    print("📡 [BT MODE] Deploying Smart Zero-Touch Bluetooth Manager...")
    threading.Thread(target=_bluetooth_background_manager, daemon=True).start()