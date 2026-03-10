import subprocess
import time
import threading

def _bluetooth_background_manager():
    """Handles automated pairing, auto-trusting, and single-device lock."""

    locked_device = None

    # Start persistent bluetoothctl session
    bt_proc = subprocess.Popen(
        ['bluetoothctl'],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True
    )

    # Initial configuration
    bt_proc.stdin.write("power on\n")
    bt_proc.stdin.write("agent NoInputNoOutput\n")
    bt_proc.stdin.write("default-agent\n")
    bt_proc.stdin.write("discoverable on\n")
    bt_proc.stdin.write("pairable on\n")
    bt_proc.stdin.write("scan on\n")
    bt_proc.stdin.flush()

    while True:
        try:
            # Keep device visible for new phones
            subprocess.run(["bluetoothctl", "discoverable", "on"], stdout=subprocess.DEVNULL)
            subprocess.run(["bluetoothctl", "pairable", "on"], stdout=subprocess.DEVNULL)

            # Get known devices
            devices_out = subprocess.run(
                ["bluetoothctl", "devices"],
                capture_output=True,
                text=True
            ).stdout

            macs = [
                line.split()[1]
                for line in devices_out.strip().split('\n')
                if line.startswith("Device")
            ]

            # Auto-trust devices
            for mac in macs:
                subprocess.run(
                    ["bluetoothctl", "trust", mac],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            # Check connected devices
            connected_out = subprocess.run(
                ["bluetoothctl", "devices", "Connected"],
                capture_output=True,
                text=True
            ).stdout

            connected_macs = [
                line.split()[1]
                for line in connected_out.strip().split('\n')
                if line.startswith("Device")
            ]

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
                        subprocess.run(
                            ["bluetoothctl", "disconnect", mac],
                            stdout=subprocess.DEVNULL
                        )

        except Exception:
            pass

        time.sleep(1)


def enable_bluetooth_pairing():
    """Starts the automated Bluetooth manager."""
    print("📡 [BT MODE] Deploying Zero-Touch Bluetooth Manager...")
    threading.Thread(
        target=_bluetooth_background_manager,
        daemon=True
    ).start()