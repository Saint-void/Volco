import time
import platform
import sys
import select
import threading # ⚡ Added for instant background tasks

# ⚡ THE SMART OS CHECKER (Replaces 'import keyboard')
IS_WINDOWS = platform.system() == "Windows"
keyboard = None
if IS_WINDOWS:
    import keyboard

def check_for_button():
    """Checks for Space/Shift on Windows, or the 'Enter' key on Linux."""
    if IS_WINDOWS and keyboard is not None:
        return keyboard.is_pressed("space") or keyboard.is_pressed("right shift")
    else:
        # Non-blocking check for the Enter key on Linux
        i, _, _ = select.select([sys.stdin], [], [], 0.0)
        if i:
            sys.stdin.readline() 
            return True
        return False

from config.config_manager import config
from core.audio_io import play_sfx, calibrate_mic
from core.wake_word import WakeWordEngine
from core.connection import ConnectionManager
from core.data_pipe import start_data_pipe
from core.bluetooth_pairing import enable_bluetooth_pairing 

from modes.ai_mode.session import start_ai_session
from modes.bt_mode.media_control import pause_media, resume_media
 

# =============================
# 🚀 THE DISPATCHER (MAIN OS)
# =============================
def main():
    print("\n--- VOLCO OS INITIALIZATION ---")
    
    # ⚡ 1. The Boot Sound
    play_sfx("./assets/sounds/boot.wav")
    time.sleep(1.5)
    
    # ⚡ 2. Initialize the Connection Manager FIRST
    conn_manager = ConnectionManager()
    
    # ⚡ 3. START BLUETOOTH & Pass the manager to the pipe!
    enable_bluetooth_pairing()
    play_sfx("./assets/sounds/bt_pairing.wav", async_play=True)
    time.sleep(1.2)
    start_data_pipe(conn_manager) # 👈 Now the pipe can wake the AI up!

    # ⚡ 4. Load the Wake Engine
    wake_engine = WakeWordEngine()
    
    # ⚡ 5. Attempt Connection (Will gracefully abort if no ID exists yet)
    conn_manager.connect()

    # ⚡ 6. Calibrate the microphone
    current_noise_floor = calibrate_mic(duration=1.0)    
    
    try:
        wake_engine.start()
            
        while True:
            # Heartbeat
            conn_manager.send_ping()
            
            # 🎧 Listen for Wake Word
            is_wake_word, pcm = wake_engine.read_and_process()
            
            # 🔘 Listen for Physical Button Press using our Smart Checker
            button_triggered = check_for_button()
            
            # ⚡ TRIGGER IF EITHER ONE HAPPENS
            # ⚡ TRIGGER IF EITHER ONE HAPPENS
            if is_wake_word or button_triggered:
                trigger_type = "BUTTON" if button_triggered else "VOICE"
                print(f"\n⚡ WAKE TRIGGERED ({trigger_type})!")
                
                # ⚡ THE AUDIO FIX: Stop the microphone immediately to prevent ALSA crashes!
                wake_engine.stop() 
                
                # Network Check
                if conn_manager.is_connected():
                    if not conn_manager.send_data("PING"):
                        print("🔌 Stale connection detected. Forcing reset...")
                
                if not conn_manager.is_connected():
                    print("🔌 Connection lost. Attempting reconnect...")
                    if not conn_manager.connect():
                        print("❌ Failed to reconnect.")
                        play_sfx(config["audio"]["sfx_offline"], async_play=True)
                        wake_engine.start() # Turn the mic back on so they can try again
                        continue
                
                try:
                    # 1️⃣ --- THE BLUETOOTH HIJACK (Instant Background Thread) ---
                    threading.Thread(target=pause_media, daemon=True).start()
                    play_sfx(config["audio"]["sfx_wake"], async_play=True)

                    # 2️⃣ --- THE AI TAKEOVER ---
                    start_ai_session(wake_engine, conn_manager, current_noise_floor)
                    
                    # 3️⃣ --- THE BLUETOOTH RESUME (Instant Background Thread) ---
                    threading.Thread(target=resume_media, daemon=True).start()
                    
                    # Reset OS back to idle
                    wake_engine.start()
                    time.sleep(0.5)   
                    print("\n✅ VOLCO OS READY | Waiting for wake word or button...")
                    
                except Exception as e:
                    print(f"⚠️ Connection lost during session. Resetting...")
                    conn_manager.close()
                    time.sleep(1)
                    wake_engine.start()

    except KeyboardInterrupt:
        print("\n👋 Shutting down Volco OS...")
        play_sfx("./assets/sounds/shutdown.wav", async_play=False)
    finally:
        conn_manager.close()
        wake_engine.cleanup()

if __name__ == "__main__":                                  
    while True:
        try:
            main()
        except BaseException as e:
            print(f"🔄 Hard Restart Triggered: {e}")
            time.sleep(2)