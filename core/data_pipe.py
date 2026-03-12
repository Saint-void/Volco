import os
import time
import threading
import subprocess
import serial

# ⚡ THE LOCK: Prevents multiple threads from fighting over the antenna
_pipe_running = False 

def _run_rfcomm_server(conn_manager):
    try:
        subprocess.run(["sudo", "killall", "rfcomm"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        time.sleep(1)
        subprocess.Popen(["sudo", "rfcomm", "watch", "/dev/rfcomm0", "1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        while True:
            if os.path.exists("/dev/rfcomm0"):
                try:
                    time.sleep(0.5) 
                    subprocess.run(["sudo", "chmod", "666", "/dev/rfcomm0"]) 

                    with serial.Serial("/dev/rfcomm0", 9600, timeout=1) as bt_serial:
                        print("\n✅ [DATA PIPE] Phone connected! Waiting for payload...")

                        while os.path.exists("/dev/rfcomm0"):
                            data = bt_serial.readline()
                            if data:
                                # Decode and ignore any weird Bluetooth background noise bytes
                                message = data.decode('utf-8', errors='ignore').strip()
                                
                                # Print everything so we know the phone is talking!
                                if message:
                                    print(f"🔍 [DEBUG DATA]: {message}") 
                                
                                if message.startswith("DB_ID:"):
                                    real_user_id = message.split(":")[1]
                                    
                                    # 💾 Use an absolute path so it forces the file to save in /core/
                                    memory_path = os.path.join(os.path.dirname(__file__), "current_user.txt")
                                    with open(memory_path, "w") as memory_file:
                                        memory_file.write(real_user_id)
                                    
                                    print(f"✅ [DATA PIPE] Profile Locked In! Saved to: {memory_path}")                                        
                            time.sleep(0.1)
                            
                except serial.SerialException as e:
                    # Linux naturally throws a SerialException when the phone disconnects
                    pass 
                except Exception as e:
                    print(f"⚠️ [DATA PIPE] Stream Error: {e}")
                finally:
                    print("🔒 [DATA PIPE] Connection closed. Ready for next sync.")
                    time.sleep(2)
            else:
                time.sleep(1)
                
    except Exception as e:
        print(f"❌ [DATA PIPE] Server crashed: {e}")

def start_data_pipe(conn_manager=None):
    global _pipe_running
    if _pipe_running:
        return # Block duplicate threads from crashing the port!
        
    _pipe_running = True
    print("📡 [DATA PIPE] Outsourcing Bluetooth Serial to Linux Kernel...")
    threading.Thread(target=_run_rfcomm_server, args=(conn_manager,), daemon=True).start()