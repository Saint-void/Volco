import time
import platform
import sys
import threading
import subprocess 

# ⚡ 1. ONLY IMPORT THE AUDIO ENGINE FIRST
from core.audio_io import play_sfx 

# ⚡ 2. PLAY THE BOOT SOUND INSTANTLY!
print("\n--- VOLCO OS INITIALIZING ---")
play_sfx("./assets/sounds/boot.wav", async_play=True)

# ⚡ 3. NOW LOAD THE HEAVY AI LIBRARIES IN THE BACKGROUND
from config.config_manager import config
from core.audio_io import calibrate_mic
from core.wake_word import WakeWordEngine
from core.connection import ConnectionManager
from core.data_pipe import start_data_pipe
from core.volco_spotify import VolcoSpotifyManager
from core.bluetooth_pairing import enable_bluetooth_pairing 
from modes.ai_mode.session import start_ai_session
from modes.ai_mode import session
from core.volco_audio_engine import VolcoSpotifyEngine

# ==========================================
# 🎵 SPOTIFY MANAGERS
# ==========================================
# Initialize them globally so everything can reach them
spotify_hw = VolcoSpotifyManager() # Controls librespot (hardware)
spotify_api = VolcoSpotifyEngine() # Controls volume/play/pause (API)

# Start the background librespot daemon
spotify_hw.start_client()

# ==========================================
# 🎵 BLUETOOTH BRIDGE MANAGER
# ==========================================
def manage_audio_bridge(action="stop"):
    subprocess.run(["killall", "bluealsa-aplay"], stderr=subprocess.DEVNULL)
    if action == "start":
        subprocess.Popen(
            ["bluealsa-aplay", "00:00:00:00:00:00"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

# ==========================================
# 🔘 GLOBAL STATE & MANAGERS
# ==========================================
IS_WINDOWS = platform.system() == "Windows"
_button_pressed_event = False

# Power State Trackers
volco_sleeping = False  
_was_held_flag = False  
conn_manager = None   

# ==========================================
# 🔘 HARDWARE BUTTON INTERRUPTS
# ==========================================
if not IS_WINDOWS:
    try:
        from gpiozero import Button #type: ignore
        
        volco_button = Button(17, bounce_time=0.1, hold_time=3.0)
        
        def button_held():
            """Fires exactly when the button has been held for 3 seconds."""
            global _was_held_flag, volco_sleeping
            _was_held_flag = True 
            
            if not volco_sleeping:
                print("\n🌙 [POWER] 3-Second Hold Detected! Entering Deep Sleep...")
                volco_sleeping = True
                threading.Thread(target=play_sfx, args=("./assets/sounds/shutdown.wav",)).start()

                # ⚡ 1. Kill the Spotify Standalone Client
                spotify_hw.stop_client()
                
                # 2. Kill Bluetooth & Audio Bridge
                manage_audio_bridge("stop")
                subprocess.run(["bluetoothctl", "power", "off"], stdout=subprocess.DEVNULL)

                
        def button_released():
            """Fires when you let go of the button."""
            global _was_held_flag, volco_sleeping, _button_pressed_event
            
            if _was_held_flag:
                _was_held_flag = False
                return
                
            if volco_sleeping:
                print("\n☀️ [POWER] Waking up Volco!")
                volco_sleeping = False
                threading.Thread(target=play_sfx, args=("./assets/sounds/boot.wav",)).start()
                time.sleep(2) 
                
                # 1. Turn the radio back on
                subprocess.run(["bluetoothctl", "power", "on"], stdout=subprocess.DEVNULL)
                threading.Thread(target=play_sfx, args=("./assets/sounds/bt_pairing.wav",)).start()
                
                # ⚡ 2. Boot the Spotify engine back up! (It auto-connects to the cache)
                print("🎵 [POWER] Starting Standalone Spotify Client...")
                spotify_hw.start_client()
                
            else:
                print("\n🚨 [HARDWARE INTERRUPT] Single click! Triggering AI...")
                session.button_pressed_flag.set()  
                # ❌ REMOVED manage_audio_bridge("stop") and pause_media here!
                # The main loop will handle ducking the volume smoothly.

        volco_button.when_held = button_held
        volco_button.when_released = button_released
        print("🔘 [HARDWARE] Smart Button (Click/Hold) initialized on GPIO 17!")
        
    except ImportError:
        print("⚠️ [HARDWARE] gpiozero not found! Button disabled.")
        

def check_for_button():
    global _button_pressed_event
    if _button_pressed_event:
        _button_pressed_event = False 
        return True
    return False

# =============================
# 🚀 THE DISPATCHER (MAIN OS)
# =============================
def main():
    global conn_manager

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
            
            # 🎧 Listen for Wake Word
            is_wake_word, pcm = wake_engine.read_and_process()
            
            # 🔘 Listen for Physical Button Press
            button_triggered = check_for_button()
            
            # ⚡ TRIGGER IF EITHER ONE HAPPENS
            if is_wake_word or button_triggered:
                trigger_type = "BUTTON" if button_triggered else "VOICE"
                print(f"\n⚡ WAKE TRIGGERED ({trigger_type})!")

                # 🔉 DUCK THE AUDIO via API
                previous_volume = spotify_api.get_current_volume()
                # Only duck if the volume is currently higher than the duck target (15)
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