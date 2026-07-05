import os
import time
import threading
from core.platform_support import can_use_rfcomm, is_macos, platform_label, run_quiet, popen_quiet

# The lock prevents multiple threads from fighting over the antenna.
_pipe_running = False


def _save_user_id(real_user_id):
    memory_path = os.path.join(os.path.dirname(__file__), "current_user.txt")
    with open(memory_path, "w") as memory_file:
        memory_file.write(real_user_id)
    print(f"✅ [DATA PIPE] Profile Locked In! Saved to: {memory_path}")


def _run_rfcomm_server(conn_manager):
    import serial

    try:
        run_quiet(["sudo", "killall", "rfcomm"])
        time.sleep(1)
        popen_quiet(["sudo", "rfcomm", "watch", "/dev/rfcomm0", "1"])

        while True:
            if os.path.exists("/dev/rfcomm0"):
                try:
                    time.sleep(0.5) 
                    run_quiet(["sudo", "chmod", "666", "/dev/rfcomm0"])

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
                                    _save_user_id(real_user_id)
                            time.sleep(0.1)
                            
                except serial.SerialException as e:
                    # Linux naturally throws a SerialException when the phone disconnects.
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
        return False

    if not can_use_rfcomm():
        if is_macos():
            print("📡 [DATA PIPE] macOS detected. Bluetooth serial RFCOMM is Pi/Linux-only; skipping.")
        else:
            print(f"📡 [DATA PIPE] Skipped on {platform_label()}: rfcomm is unavailable.")
        return False
        
    _pipe_running = True
    print("📡 [DATA PIPE] Outsourcing Bluetooth Serial to Linux Kernel...")
    threading.Thread(target=_run_rfcomm_server, args=(conn_manager,), daemon=True).start()
    return True
