import time
import keyboard # ⚡ NEW: Import keyboard for the physical button
from config.config_manager import config
from core.audio_io import play_sfx, calibrate_mic
from core.wake_word import WakeWordEngine
from core.connection import ConnectionManager
from core.bluetooth_pairing import enable_bluetooth_pairing # ⚡ NEW: Import Bluetooth manager

from modes.ai_mode.session import start_ai_session
from modes.bt_mode.media_control import pause_media, resume_media

# =============================
# 🚀 THE DISPATCHER (MAIN OS)
# =============================
def main():
    print("\n--- VOLCO OS INITIALIZATION ---")
    
    # ⚡ 1. Start speaking in the background
    play_sfx("./assets/sounds/boot.wav", async_play=True)
    
    # 2. Do the heavy lifting in the background
    wake_engine = WakeWordEngine()
    conn_manager = ConnectionManager()
    conn_manager.connect()

    # ⚡ 3. THE TRAFFIC LIGHT: Give the boot voice time to finish!
    # If your boot.wav is exactly 1 second long, wait 1.2 seconds just to be safe.
    time.sleep(1.2) 

    # 4. Turn on Bluetooth (This triggers bt_pairing.wav)
    enable_bluetooth_pairing()
    
    # 5. Calibrate the microphone
    current_noise_floor = calibrate_mic(duration=1.0)

    print(f"\n✅ VOLCO OS READY | Waiting for wake word or 'Space' button...")
    
    try:
        wake_engine.start()
        
        while True:
            # Heartbeat
            conn_manager.send_ping()
            
            # 🎧 Listen for Wake Word
            is_wake_word, pcm = wake_engine.read_and_process()
            
            # 🔘 Listen for Physical Button Press (Simulating a hardware button on the headset)
            is_button_pressed = keyboard.is_pressed("space")
            
            # ⚡ TRIGGER IF EITHER ONE HAPPENS
            if is_wake_word or is_button_pressed:
                trigger_type = "BUTTON" if is_button_pressed else "VOICE"
                print(f"\n⚡ WAKE TRIGGERED ({trigger_type})!")
                
                # Network Check
                if conn_manager.is_connected():
                    if not conn_manager.send_data("PING"):
                        print("🔌 Stale connection detected. Forcing reset...")
                
                if not conn_manager.is_connected():
                    print("🔌 Connection lost. Attempting reconnect...")
                    if not conn_manager.connect():
                        print("❌ Failed to reconnect.")
                        play_sfx(config["audio"]["sfx_offline"], async_play=True)
                        continue
                
                try:
                    wake_engine.stop()
                    
                    # 1️⃣ --- THE BLUETOOTH HIJACK ---
                    pause_media()
                    play_sfx(config["audio"]["sfx_wake"], async_play=True)

                    # 2️⃣ --- THE AI TAKEOVER ---
                    start_ai_session(wake_engine, conn_manager, current_noise_floor)
                    
                    # 3️⃣ --- THE BLUETOOTH RESUME ---
                    resume_media()
                    
                    # Reset OS back to idle
                    wake_engine.start()
                    # A small sleep prevents holding the spacebar from triggering it twice instantly
                    time.sleep(0.5) 
                    print("\n✅ VOLCO OS READY | Waiting for wake word or button...")
                    
                except Exception as e:
                    print(f"⚠️ Connection lost during session. Resetting...")
                    conn_manager.close()
                    time.sleep(1)
                    wake_engine.start()

    except KeyboardInterrupt:
        print("\n👋 Shutting down Volco OS...")
        # ⚡ VUI 2: The Shutdown Sequence (async_play=False so it doesn't instantly close before playing)
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