import subprocess
import time
import threading

from core.audio_io import play_sfx

def _bluetooth_background_manager():
    """Smart Vault: Only handles visibility and intruder kicking. NO AGENTS."""
    locked_device = None

    # Initial Wake Up
    subprocess.run(["bluetoothctl", "power", "on"], stdout=subprocess.DEVNULL)
    subprocess.run(["bluetoothctl", "discoverable", "on"], stdout=subprocess.DEVNULL)
    subprocess.run(["bluetoothctl", "pairable", "on"], stdout=subprocess.DEVNULL)

    while True:
        try:
            # Check who is connected
            connected_out = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True).stdout
            connected_macs = [line.split()[1] for line in connected_out.strip().split('\n') if line.startswith("Device")]

            if len(connected_macs) == 0:
                if locked_device is not None:
                    print("\n🔓 [BT MODE] Device disconnected. Volco is free.")
                    locked_device = None
                    subprocess.run(["bluetoothctl", "discoverable", "on"], stdout=subprocess.DEVNULL)

            elif len(connected_macs) == 1:
                if locked_device is None:
                    locked_device = connected_macs[0]
                    print(f"\n🔒 [BT MODE] Locked to device: {locked_device}")
                    play_sfx("./assets/sounds/bt_connected.wav")
                    subprocess.run(["bluetoothctl", "trust", locked_device], stdout=subprocess.DEVNULL)
                    subprocess.run(["bluetoothctl", "discoverable", "off"], stdout=subprocess.DEVNULL)

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