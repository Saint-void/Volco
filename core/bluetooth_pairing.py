import subprocess
import time
import threading
from core.audio_io import play_sfx

def _bluetooth_background_manager():
    """Smart Vault: Handles visibility, auto-connections, and intruder kicking."""
    locked_device = None

    # 1. Turn on the antenna
    subprocess.run(["bluetoothctl", "power", "on"], stdout=subprocess.DEVNULL)
    
    # ⚡ THE FIX: Tell Linux to STOP asking for PINs permanently
    # This sets the "NoInputNoOutput" mode so it "Just Works"
    subprocess.run(["bluetoothctl", "agent", "NoInputNoOutput"], stdout=subprocess.DEVNULL)
    subprocess.run(["bluetoothctl", "default-agent"], stdout=subprocess.DEVNULL)
    
    # Optional: Set the broadcast name so your phone sees "Volco Headset"
    subprocess.run(["bluetoothctl", "system-alias", "Volco"], stdout=subprocess.DEVNULL)

    time.sleep(1) 

    # 2. Initial Boot Check
    connected_out = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True).stdout
    connected_macs = [line.split()[1] for line in connected_out.strip().split('\n') if line.startswith("Device")]

    if len(connected_macs) > 0:
        locked_device = connected_macs[0]
        print(f"\n🔒 [BT MODE] Auto-locked to existing device on boot: {locked_device}")
        play_sfx("./assets/sounds/bt_connected.wav")
        subprocess.run(["bluetoothctl", "discoverable", "off"], stdout=subprocess.DEVNULL)
        subprocess.run(["bluetoothctl", "pairable", "off"], stdout=subprocess.DEVNULL)
    else:
        # If nobody is connected, open the vault doors for pairing
        print("\n🔓 [BT MODE] No known devices found. Entering Pairing Mode...")
        
        # ⚡ ADD THIS LINE RIGHT HERE!
        play_sfx("./assets/sounds/bt_pairing.wav") 
        
        subprocess.run(["bluetoothctl", "discoverable", "on"], stdout=subprocess.DEVNULL)
        subprocess.run(["bluetoothctl", "pairable", "on"], stdout=subprocess.DEVNULL)


    # 3. Start the normal monitoring loop
    while True:
        try:
            connected_out = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True).stdout
            connected_macs = [line.split()[1] for line in connected_out.strip().split('\n') if line.startswith("Device")]

            if len(connected_macs) == 0:
                if locked_device is not None:
                    print("\n🔓 [BT MODE] Device disconnected. Volco is free.")
                    locked_device = None
                    subprocess.run(["bluetoothctl", "discoverable", "on"], stdout=subprocess.DEVNULL)
                    subprocess.run(["bluetoothctl", "pairable", "on"], stdout=subprocess.DEVNULL)

            elif len(connected_macs) == 1:
                if locked_device is None:
                    # ⚡ THIS IS A NEW CONNECTION
                    locked_device = connected_macs[0]
                    print(f"\n🔒 [BT MODE] Locked to new device: {locked_device}")
                    play_sfx("./assets/sounds/bt_connected.wav")
                    subprocess.run(["bluetoothctl", "trust", locked_device], stdout=subprocess.DEVNULL)
                    subprocess.run(["bluetoothctl", "discoverable", "off"], stdout=subprocess.DEVNULL)
                    subprocess.run(["bluetoothctl", "pairable", "off"], stdout=subprocess.DEVNULL)

            elif len(connected_macs) > 1:
                for mac in connected_macs:
                    if mac != locked_device:
                        print(f"\n🛡️ [BT MODE] Intruder blocked! Kicking MAC: {mac}")
                        subprocess.run(["bluetoothctl", "disconnect", mac], stdout=subprocess.DEVNULL)

        except Exception:
            pass
        time.sleep(2)

def enable_bluetooth_pairing():
    print("📡 [BT MODE] Deploying Smart Vault...")
    threading.Thread(target=_bluetooth_background_manager, daemon=True).start()