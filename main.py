import time
from config.config_manager import config
from core.audio_io import play_sfx, calibrate_mic
from core.wake_word import WakeWordEngine
from core.connection import ConnectionManager
from modes.bt_mode.media_control import pause_media, resume_media

# ⚡ NEW: Import our modular AI Session
from modes.ai_mode.session import start_ai_session

# =============================
# 🚀 THE DISPATCHER (MAIN OS)
# =============================
def main():
    print("\n--- VOLCO OS INITIALIZATION ---")
    current_noise_floor = calibrate_mic(duration=1.0)

    wake_engine = WakeWordEngine()
    conn_manager = ConnectionManager()
    conn_manager.connect()

    print(f"\n✅ VOLCO OS READY | Waiting for wake word...")
    
    try:
        wake_engine.start()
        
        while True:
            # Heartbeat
            conn_manager.send_ping()
            
            # Listen for Wake Word
            is_wake_word, pcm = wake_engine.read_and_process()
            
            if is_wake_word:
                print("\n⚡ WAKE WORD DETECTED!")
                
                if conn_manager.is_connected():
                    if not conn_manager.send_data("PING"):
                        print("🔌 Stale connection detected. Forcing reset...")
                
                if not conn_manager.is_connected():
                    print("🔌 Connection lost. Attempting reconnect...")
                    if not conn_manager.connect():
                        print("❌ Failed to reconnect.")
                        play_sfx(config["audio"]["sfx_sleep"], async_play=True)
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
                    print("\n✅ VOLCO OS READY | Waiting for wake word...")
                    
                except Exception as e:
                    print(f"⚠️ Connection lost during session. Resetting...")
                    conn_manager.close()
                    time.sleep(1)
                    wake_engine.start()

    except KeyboardInterrupt:
        print("\n👋 Shutting down Volco OS...")
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