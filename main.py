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

# Power State Trackers
volco_sleeping = False
ai_session_active = False
_was_held_flag = False
conn_manager = None

# New Trigger Events for the threaded engine
trigger_event = threading.Event()
trigger_type = "VOICE"

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
            global _was_held_flag, volco_sleeping, ai_session_active, trigger_event, trigger_type

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

            elif ai_session_active:
                print("\n🔘 [HARDWARE] AI already active; button press ignored.")

            else:
                print("\n🚨 [HARDWARE INTERRUPT] Single click! Triggering AI...")
                trigger_type = "BUTTON"
                trigger_event.set()

        volco_button.when_held = button_held
        volco_button.when_released = button_released
        print("🔘 [HARDWARE] Smart Button (Click/Hold) initialized on GPIO 17!")

    except ImportError:
        print("⚠️ [HARDWARE] gpiozero not found! Button disabled.")


def wake_word_worker(wake_engine):
    """Background thread to listen for the wake word without blocking the OS."""
    global trigger_event, trigger_type, volco_sleeping
    
    if not wake_engine.is_functional:
        print("❌ [WAKE THREAD] Engine not functional. Thread exiting.")
        return

    print("👂 [WAKE THREAD] Background listener active and waiting for audio...")
    
    while True:
        if not volco_sleeping:
            # Wait for stream to be ready if it's not yet
            if wake_engine.audio_stream is None:
                time.sleep(0.1)
                continue

            is_wake, confidence = wake_engine.read_and_process()
            if is_wake:
                print(f"🎯 [WAKE THREAD] Match found! Confidence: {confidence:.2f}")
                trigger_type = "VOICE"
                trigger_event.set()
        else:
            time.sleep(0.5)

# =============================
# 🚀 THE DISPATCHER (MAIN OS)
# =============================
def main():
    global conn_manager, trigger_event, trigger_type, volco_sleeping, ai_session_active

    print("\n--- VOLCO OS CORE BOOT ---")

    conn_manager = ConnectionManager()
    
    print("🔵 [BOOT] Initializing Bluetooth stack...")
    enable_bluetooth_pairing()
    manage_audio_bridge("start")

    start_data_pipe(conn_manager)

    print("🧠 [BOOT] Initializing AI systems...")
    print("🧠 [DEBUG] Initializing WakeWordEngine...")
    wake_engine = WakeWordEngine()
    print("🧠 [DEBUG] WakeWordEngine initialized.")

    print("🧠 [DEBUG] Connecting to server...")
    conn_manager.connect()
    print("🧠 [DEBUG] Connected to server.")

    print("🧠 [DEBUG] Calibrating microphone...")
    current_noise_floor = calibrate_mic(duration=1.0)
    print(f"🧠 [DEBUG] Microphone calibrated. Noise floor: {current_noise_floor}")

    # ⚡ PRE-CACHE SPOTIFY
    print("🎵 [BOOT] Pre-caching Spotify credentials...")                                  
    threading.Thread(target=spotify_api._get_access_token, daemon=True).start() 

    # Start the dedicated Wake Word thread
    threading.Thread(target=wake_word_worker, args=(wake_engine,), daemon=True).start()

    print("✅ VOLCO OS BOOT COMPLETE") 
    
    try:
        wake_engine.start()
        was_sleeping_loop_state = False 
            
        while True:
           # 🛌 1. THE DEEP SLEEP CHECK
            if volco_sleeping:
                if not was_sleeping_loop_state:
                    print("💤 OS suspending background tasks to save power...")
                    wake_engine.stop() 
                    conn_manager.close()
                    was_sleeping_loop_state = True
                
                time.sleep(0.5) 
                continue 
                
            # ☀️ 2. THE WAKE UP RECOVERY
            if was_sleeping_loop_state:
                print("⚡ OS resuming background tasks...")
                wake_engine.start() 
                was_sleeping_loop_state = False

            # Heartbeat
            conn_manager.send_ping()
            
            # 🎧 3. THE TRIGGER CHECK (Wait for Voice or Button)
            if trigger_event.wait(timeout=0.1):
                print(f"\n⚡ WAKE TRIGGERED ({trigger_type})!")
                trigger_event.clear()

                # 🔉 DUCK THE AUDIO
                previous_volume = spotify_api.get_current_volume()
                duck_target = 15
                if previous_volume > duck_target:
                    spotify_api.fade_volume(target_volume=duck_target, start_volume=previous_volume)                
                
                wake_engine.stop() 
                time.sleep(0.2)
                
                # Network Check
                if not conn_manager.is_connected():
                    print("🔌 Connection lost. Attempting reconnect...")
                    if not conn_manager.connect():
                        print("❌ Failed to reconnect.")
                        if previous_volume > duck_target:
                            spotify_api.fade_volume(target_volume=previous_volume, start_volume=duck_target)
                        wake_engine.start() 
                        continue
                
                try:
                    # 1️⃣ --- THE WAKE SOUND (Now Async!) ---
                    play_sfx(config["audio"]["sfx_wake"], async_play=True)

                    # 2️⃣ --- THE AI TAKEOVER ---
                    ai_session_active = True
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
                finally:
                    ai_session_active = False
                    
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
