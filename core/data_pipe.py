import os
import time
import threading
import subprocess
import serial

# Pass conn_manager into the background thread
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
                        print("\n✅ [DATA PIPE] Phone connected to Kernel Pipe!")

                        while os.path.exists("/dev/rfcomm0"):
                            data = bt_serial.readline()
                            if data:
                                message = data.decode('utf-8').strip()
                                if message.startswith("DB_ID:"):
                                    real_user_id = message.split(":")[1]
                                    
                                    # 💾 Save to memory
                                    with open("core/current_user.txt", "w") as memory_file:
                                        memory_file.write(real_user_id)
                                    
                                    print(f"✅ [DATA PIPE] Profile Locked In! Volco now belongs to: {real_user_id}")
                                    
                                    # ⚡ INSTANTLY WAKE UP THE AI CONNECTION!
                                    if conn_manager and not conn_manager.is_connected():
                                        print("🚀 [DATA PIPE] Triggering Vella Server connection...")
                                        conn_manager.connect()
                                        
                            time.sleep(0.1)
                            
                except serial.SerialException:
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

# Accept the conn_manager as an argument
def start_data_pipe(conn_manager=None):
    print("📡 [DATA PIPE] Outsourcing Bluetooth Serial to Linux Kernel...")
    threading.Thread(target=_run_rfcomm_server, args=(conn_manager,), daemon=True).start()