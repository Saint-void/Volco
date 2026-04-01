import subprocess
import time

def check_internet():
    """Pings Google's DNS to see if we have an active internet connection."""
    try:
        # Send 1 ping packet, wait up to 2 seconds for a reply
        output = subprocess.run(
            ["ping", "-c", "1", "-W", "2", "8.8.8.8"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        return output.returncode == 0
    except Exception as e:
        print(f"⚠️ Network check error: {e}")
        return False

def start_hotspot_and_portal():
    """Failsafe mode: Broadcasts the 'Volco Setup' network and launches the UI."""
    print("📡 No internet detected. Initiating Volco Setup Hotspot...")
    
    # 1. Start the NetworkManager Hotspot (Open network, no password so the portal pops up easily)
    subprocess.run(["sudo", "nmcli", "dev", "wifi", "hotspot", "ifname", "wlan0", "ssid", "Volco Setup"], check=False)    
    # 2. Restart dnsmasq to ensure the DNS trap is active
    subprocess.run(["sudo", "systemctl", "restart", "dnsmasq"], check=False)
    
    # 3. Launch your Flask web portal
    print("🌐 Launching Captive Portal UI...")
    subprocess.run(["sudo", "python3", "volco_captive_portal.py"])

def start_volco_os():
    """Normal boot mode: Connects to Vella and starts Spotify."""
    print("✅ Internet confirmed. Booting Volco OS...")
    
    # Make sure the hotspot is turned off if it was left on
    subprocess.run(["nmcli", "connection", "down", "Hotspot"], capture_output=True)
    
    # Launch your main AI engine
    subprocess.run(["python3", "main.py"])

if __name__ == "__main__":
    print("⚡ Volco Boot Manager Initializing...")
    
    # Give the Pi's Wi-Fi chip 10 seconds to handshake with the home router
    time.sleep(10) 
    
    if check_internet():
        start_volco_os()
    else:
        start_hotspot_and_portal()