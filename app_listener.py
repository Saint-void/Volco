import socket
import json
import threading
from pathlib import Path

CURRENT_USER_PATH = Path(__file__).resolve().parent / "core" / "current_user.txt"

def start_app_listener():
    """Opens a Bluetooth Data Pipe to listen for the mobile app."""
    try:
        # Create a Bluetooth Serial Socket (RFCOMM)
        server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        
        # Bind to port 1 (The standard Bluetooth Serial port)
        server_sock.bind((socket.BDADDR_ANY, 1))
        server_sock.listen(1)
        
        print("📱 [APP MODE] Data Pipe open! Waiting for the mobile app to send credentials...")
        
        while True:
            client_sock, client_info = server_sock.accept()
            print(f"✅ [APP MODE] App connected from {client_info[0]}!")
            
            try:
                # Wait for the app to send data
                data = client_sock.recv(1024).decode("utf-8")
                if data:
                    print(f"📥 [APP MODE] Received Data: {data}")
                    
                    # Parse the JSON data from the app
                    app_payload = json.loads(data)
                    user_id = app_payload.get("user_id")
                    
                    if user_id:
                        print(f"🔑 [APP MODE] Success! Volco is now assigned to Vella User: {user_id}")
                        CURRENT_USER_PATH.write_text(f"{user_id.strip()}\n", encoding="utf-8")
                        
                    # Send a success message back to the phone screen
                    client_sock.send("Credentials Accepted!".encode("utf-8"))
                    
            except Exception as e:
                print(f"⚠️ [APP MODE] Data error: {e}")
            finally:
                client_sock.close()
                
    except Exception as e:
        print(f"⚠️ [APP MODE] Failed to start App Listener: {e}")

if __name__ == "__main__":
    start_app_listener()
