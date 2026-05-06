import time
import threading
from core.connection import ConnectionManager
from core.audio_io import calibrate_mic, play_sfx
from core.volco_spotify import VolcoSpotifyEngine
from core.wake_word import WakeWordEngine
from core.bluetooth_pairing import enable_bluetooth_pairing, manage_audio_bridge
from core.data_pipe import start_data_pipe
from modes.ai_mode.session import start_ai_session
from config.config_manager import config

# Global State
volco_sleeping = False
_button_pressed_event = False
trigger_event = threading.Event()
trigger_type = "VOICE"

spotify_api = VolcoSpotifyEngine()

def handle_button():
    global _button_pressed_event, trigger_event, trigger_type
    _button_pressed_event = True
    trigger_type = "BUTTON"
    trigger_event.set()

def check_for_button():
    global _button_pressed_event
    if _button_pressed_event:
        _button_pressed_event = False 
        return True
    return False

def wake_word_worker(wake_engine):
    global trigger_event, trigger_type, volco_sleeping
    while True:
        if not volco_sleeping and wake_engine.is_functional:
            is_wake, confidence = wake_engine.read_and_process()
            if is_wake:
                trigger_type = "VOICE"
                trigger_event.set()
        else:
            time.sleep(0.1)

# =============================
# 🚀 THE DISPATCHER (MAIN OS)
# =============================
def main():
    global conn_manager, trigger_event, trigger_type, volco_sleeping

    print("\n--- VOLCO OS CORE BOOT ---")

    conn_manager = ConnectionManager()
    
    print("🔵 [BOOT] Initializing Bluetooth stack...")
    enable_bluetooth_pairing()
    manage_audio_bridge("start")

    start_data_pipe(conn_manager)

    print("🧠 [BOOT] Initializing AI systems...")
    wake_engine = WakeWordEngine()
    conn_manager.connect()
    current_noise_floor = calibrate_mic(duration=1.0)

    # ⚡ PRE-CACHE SPOTIFY (Reduces first-wake latency)                                    
    print("🎵 [BOOT] Pre-caching Spotify credentials...")                                  
    threading.Thread(target=spotify_api._get_access_token, daemon=True).start() 

    # Start the dedicated Wake Word thread
    threading.Thread(target=wake_word_worker, args=(wake_engine,), daemon=True).start()

    print("✅ VOLCO OS BOOT COMPLETE") 
    
    try:
        wake_engine.start()
        
        # Track what the loop was doing so we know when to turn the mic back on
        was_sleeping_loop_state = False 
            
        while True:
           # 🛌 1. THE DEEP SLEEP CHECK
            if volco_sleeping:
                if not was_sleeping_loop_state:
                    print("💤 OS suspending background tasks to save power...")
                    wake_engine.stop() 
                    conn_manager.close() # ⚡ Drop the backend Vella connection!
                    was_sleeping_loop_state = True
                
                time.sleep(0.5) 
                continue 
                
            # ☀️ 2. THE WAKE UP RECOVERY
            if was_sleeping_loop_state:
                print("⚡ OS resuming background tasks...")
                wake_engine.start() 
                was_sleeping_loop_state = False

            # --- YOUR NORMAL LOOP STARTS HERE ---
            # Heartbeat
            conn_manager.send_ping()
            
            # 🎧 Check if anything triggered
            if trigger_event.wait(timeout=0.1):
                print(f"\n⚡ WAKE TRIGGERED ({trigger_type})!")
                trigger_event.clear()

                # 🔉 DUCK THE AUDIO via API
                previous_volume = spotify_api.get_current_volume()
                duck_target = 15
                if previous_volume > duck_target:
                    spotify_api.fade_volume(target_volume=duck_target, start_volume=previous_volume)                
                
                wake_engine.stop() 
                time.sleep(0.2)
                
                # Network Check
                if conn_manager.is_connected():
                    if not conn_manager.send_data("PING"):
                        print("🔌 Stale connection detected. Forcing reset...")
                
                if not conn_manager.is_connected():
                    print("🔌 Connection lost. Attempting reconnect...")
                    if not conn_manager.connect():
                        print("❌ Failed to reconnect.")
                        if previous_volume > duck_target:
                            spotify_api.fade_volume(target_volume=previous_volume, start_volume=duck_target)
                        wake_engine.start() 
                        continue
                
                try:
                    # 1️⃣ --- THE WAKE SOUND ---
                    play_sfx(config["audio"]["sfx_wake"])

                    # 2️⃣ --- THE AI TAKEOVER ---
                    start_ai_session(wake_engine, conn_manager, current_noise_floor)
                    
                    # 3️⃣ --- THE BLUETOOTH RESUME ---
                    print("✅ Session ended. Resuming media volume...")
                    if previous_volume > duck_target:
                        spotify_api.fade_volume(target_volume=previous_volume, start_volume=duck_target)                   
                    
                    wake_engine.start()
                    time.sleep(0.5)   
                    print("\n✅ VOLCO OS READY | Waiting for wake word or button...")
                    
                except Exception as e:
                    print(f"⚠️ Error during session: {e}")
                    if previous_volume > duck_target:
                        spotify_api.fade_volume(target_volume=previous_volume, start_volume=duck_target)
                    conn_manager.close()
                    wake_engine.start()
                    
    except KeyboardInterrupt:
        print("\n👋 Shutting down Volco OS...")
        manage_audio_bridge("stop")
        play_sfx("./assets/sounds/shutdown.wav")
    finally:
        manage_audio_bridge("stop")
        conn_manager.close()
        wake_engine.cleanup()

if __name__ == "__main__":                                  
    while True:
        try:
            main()
        except BaseException as e:
            print(f"🔄 Hard Restart Triggered: {e}")
            time.sleep(2)
