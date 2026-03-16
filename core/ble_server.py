import json
import os
from bluezero import peripheral
from bluezero import adapter  # ⚡ NEW IMPORT

# ⚡ MUST MATCH THE REACT APP EXACTLY
SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0'
CHAR_UUID = 'abcdef01-1234-5678-1234-56789abcdef0'

def on_write(value, options):
    """This function triggers the second your React app beams the data."""
    # Convert the raw Bluetooth bytes back into a readable string
    payload_str = bytes(value).decode('utf-8')
    print(f"\n📦 Incoming BLE Data Detected!")
    
    try:
        # Parse the JSON payload sent from the React app
        data = json.loads(payload_str)
        
        if data.get("type") == "SPOTIFY_AUTH":
            refresh_token = data.get("refresh_token")
            print(f"🔑 Successfully caught Spotify Refresh Token!")
            
            # Save the token securely to the Pi's brain
            save_path = os.path.expanduser("~/volco_spotify_creds.json")
            with open(save_path, "w") as f:
                json.dump(data, f)
                
            print(f"✨ Credentials saved to {save_path}. Headset is provisioned!")
            # (Later, we will add 2 lines of code here to restart Raspotify automatically)
            
    except Exception as e:
        print(f"❌ Failed to parse data: {e}")

def main():
    print("📡 Starting Volco BLE Provisioning Server...")
    
    # ⚡ THE FIX: Automatically find the Pi's Bluetooth MAC Address
    dongles = list(adapter.Adapter.available())
    if not dongles:
        print("❌ Error: No Bluetooth adapter found. Is Bluetooth turned on?")
        return
        
    adapter_address = dongles[0].address
    print(f"🔗 Using Bluetooth Antenna: {adapter_address}")
    print("Waiting for Volco App to beam credentials...")
    
    # Create the BLE Peripheral using the real MAC address
    volco_device = peripheral.Peripheral(adapter_address, local_name='Volco')
    
    # Add our custom Provisioning Service
    volco_device.add_service(srv_id=1, uuid=SERVICE_UUID, primary=True)
    
    # Add the Characteristic (The "Inbox" where the app writes the token)
    volco_device.add_characteristic(
        srv_id=1, chr_id=1, uuid=CHAR_UUID,
        value=[], notifying=False,
        flags=['write', 'write-without-response'],
        write_callback=on_write,
        read_callback=None,
        notify_callback=None
    )
    
    # Start broadcasting!
    volco_device.publish()

if __name__ == '__main__':
    main()