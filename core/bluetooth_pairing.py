import time
import threading
from core.audio_io import play_sfx
from core.platform_support import can_use_bluez, is_macos, platform_label, run_quiet


def _btctl(*args, capture_output=False):
    return run_quiet(["bluetoothctl", *args], capture_output=capture_output)


def set_bluetooth_power(enabled):
    if not can_use_bluez():
        return False
    state = "on" if enabled else "off"
    _btctl("power", state)
    return True


def _connected_macs():
    result = _btctl("devices", "Connected", capture_output=True)
    if result is None:
        return []
    return [
        line.split()[1]
        for line in result.stdout.strip().split("\n")
        if line.startswith("Device") and len(line.split()) >= 2
    ]


def _set_pairing_open(enabled):
    state = "on" if enabled else "off"
    _btctl("discoverable", state)
    _btctl("pairable", state)


def _prepare_bluez_adapter():
    set_bluetooth_power(True)
    _btctl("agent", "NoInputNoOutput")
    _btctl("default-agent")
    _btctl("system-alias", "Volco")


def _bluetooth_background_manager():
    """Smart Vault: Handles visibility, auto-connections, and intruder kicking."""
    locked_device = None

    _prepare_bluez_adapter()
    time.sleep(1)

    connected_macs = _connected_macs()

    if len(connected_macs) > 0:
        locked_device = connected_macs[0]
        print(f"\n🔒 [BT MODE] Auto-locked to existing device on boot: {locked_device}")
        play_sfx("./assets/sounds/bt_connected.wav")
        _set_pairing_open(False)
    else:
        print("\n🔓 [BT MODE] No known devices found. Entering Pairing Mode...")
        play_sfx("./assets/sounds/bt_pairing.wav")
        time.sleep(2)
        _set_pairing_open(True)

    while True:
        try:
            connected_macs = _connected_macs()

            if len(connected_macs) == 0:
                if locked_device is not None:
                    print("\n🔓 [BT MODE] Device disconnected. Volco is free.")
                    locked_device = None
                    _set_pairing_open(True)

            elif len(connected_macs) == 1:
                if locked_device is None:
                    locked_device = connected_macs[0]
                    print(f"\n🔒 [BT MODE] Locked to new device: {locked_device}")
                    play_sfx("./assets/sounds/bt_connected.wav")
                    _btctl("trust", locked_device)
                    _set_pairing_open(False)

            elif len(connected_macs) > 1:
                for mac in connected_macs:
                    if mac != locked_device:
                        print(f"\n🛡️ [BT MODE] Intruder blocked! Kicking MAC: {mac}")
                        _btctl("disconnect", mac)

        except Exception as e:
            print(f"⚠️ [BT MODE] Monitor error: {e}")
        time.sleep(2)


def enable_bluetooth_pairing():
    if not can_use_bluez():
        if is_macos():
            print("📡 [BT MODE] macOS detected. Pair/connect Volco audio in System Settings > Bluetooth.")
        else:
            print(f"📡 [BT MODE] Smart Vault skipped on {platform_label()}: bluetoothctl is unavailable.")
        return False

    print("📡 [BT MODE] Deploying Smart Vault...")
    threading.Thread(target=_bluetooth_background_manager, daemon=True).start()
    return True
