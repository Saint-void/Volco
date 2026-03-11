import socket
import threading

def _run_bluetooth_server():
    """Runs the RFCOMM server in the background."""
    try:
        # 1. Open a Bluetooth Serial Socket (RFCOMM)
        server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        
        # 2. Bind to Port 1 (The standard Serial Port)
        server_sock.bind(("", 1))
        server_sock.listen(1)
        
        while True:
            # 3. Wait for the phone to connect
            client_sock, client_info = server_sock.accept()
            print(f"\n✅ [DATA PIPE] Phone connected! MAC: {client_info[0]}")
            
            try:
                # 4. Catch the data coming from the app
                data = client_sock.recv(1024)
                if data:
                    message = data.decode('utf-8').strip()
                    print(f"📦 [DATA PIPE] PAYLOAD RECEIVED: {message}")
                    
                    # TODO: Save to config.json later
            except Exception as e:
                print(f"⚠️ [DATA PIPE] Error reading data: {e}")
            finally:
                client_sock.close()
                
    except Exception as e:
        print(f"❌ [DATA PIPE] Server failed to start: {e}")

def start_data_pipe():
    """Deploys the listener as a silent background thread."""
    print("📡 [DATA PIPE] Listening for Volco App on RFCOMM Port 1...")
    threading.Thread(target=_run_bluetooth_server, daemon=True).start()