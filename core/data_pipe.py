import os
import time
import threading
import subprocess
import serial

def _run_rfcomm_server():
    try:
        # 1. Kill any frozen Bluetooth pipes from previous crashes
        subprocess.run(["sudo", "killall", "rfcomm"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        time.sleep(1)

        # 2. Command the Linux Kernel to catch the Bluetooth data on Channel 1
        subprocess.Popen(["sudo", "rfcomm", "watch", "/dev/rfcomm0", "1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        while True:
            # 3. Wait for the phone to connect and trigger the file creation
            if os.path.exists("/dev/rfcomm0"):
                try:
                    time.sleep(0.5) # Give Linux a millisecond to stabilize the port
                    subprocess.run(["sudo", "chmod", "666", "/dev/rfcomm0"]) # Unlock it for Python

                    # 4. Open the virtual serial pipe and read the data
                    with serial.Serial("/dev/rfcomm0", 9600, timeout=1) as bt_serial:
                        print("\n✅ [DATA PIPE] Phone connected to Kernel Pipe!")

                        while os.path.exists("/dev/rfcomm0"):
                            data = bt_serial.readline()
                            if data:
                                message = data.decode('utf-8').strip()
                                if message:
                                    print(f"📦 [DATA PIPE] PAYLOAD RECEIVED: {message}")
                                    
                            time.sleep(0.1)
                            
                except serial.SerialException:
                    pass # Phone disconnected naturally
                except Exception as e:
                    print(f"⚠️ [DATA PIPE] Stream Error: {e}")
                finally:
                    print("🔒 [DATA PIPE] Connection closed. Ready for next sync.")
                    time.sleep(2)
            else:
                time.sleep(1)
                
    except Exception as e:
        print(f"❌ [DATA PIPE] Server crashed: {e}")

def start_data_pipe():
    print("📡 [DATA PIPE] Outsourcing Bluetooth Serial to Linux Kernel...")
    threading.Thread(target=_run_rfcomm_server, daemon=True).start()