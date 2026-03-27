import sys
import subprocess
import time

def connect_to_wifi(ssid, password):
    # 1. Wait a moment to let the Flask server send the "Success" screen to the phone
    time.sleep(3)
    
    # 2. Turn off the Volco hotspot
    subprocess.run(["nmcli", "connection", "down", "VolcoSetupHotspot"], capture_output=True)
    
    # 3. Tell NetworkManager to connect to the new user-provided network
    print(f"Connecting to {ssid}...")
    cmd = ["nmcli", "dev", "wifi", "connect", ssid, "password", password]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if "successfully" in result.stdout:
        print("✅ Connected to new network!")
        # Optional: Have Vella say "Connected to Wi-Fi" here!
    else:
        print(f"❌ Failed to connect: {result.stderr}")
        # If it fails, reboot back into hotspot mode

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        connect_to_wifi(sys.argv[1], sys.argv[2])