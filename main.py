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
from modes.bt_mode.media_control import pause_media, resume_media
from modes.ai_mode import session  

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

# ⚡ NEW: Initialize Spotify globally so the hardware buttons can control it!
# Notice we DO NOT pass a username/password. It uses the cached SSO token.
spotify = VolcoSpotifyManager()

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
                spotify.stop_client()
                
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
                spotify.start_client()

                # ... (Keep your aggressive_reconnect code here, it's perfect) ...
                
            else:
                print("\n🚨 [HARDWARE INTERRUPT] Single click! Triggering AI...")
                session.button_pressed_flag.set()  
                threading.Thread(target=pause_media, daemon=True).start()
                manage_audio_bridge("stop")

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
    # Note: 'spotify' is already global, no need to declare it here

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

    # ⚡ BOOT SPOTIFY AT STARTUP
    print("🎵 [BOOT] Activating Spotify Standalone Client...")
    spotify.start_client()

    print("✅ VOLCO OS BOOT COMPLETE") 
    
    # ... (Keep the rest of your while True loop exactly as you have it!) ...
    
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
                # ❌ We removed conn_manager.connect() from here!
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
                
                # Double-tap the locks just to be safe if triggered by voice
                manage_audio_bridge("stop")
                threading.Thread(target=pause_media, daemon=True).start()
                
                # ⚡ Stop the microphone immediately to prevent ALSA crashes!
                wake_engine.stop() 
                time.sleep(0.5) # Let the hardware breathe
                
                # Network Check
                if conn_manager.is_connected():
                    if not conn_manager.send_data("PING"):
                        print("🔌 Stale connection detected. Forcing reset...")
                
                if not conn_manager.is_connected():
                    print("🔌 Connection lost. Attempting reconnect...")
                    if not conn_manager.connect():
                        print("❌ Failed to reconnect.")
                        play_sfx(config["audio"]["sfx_offline"])
                        manage_audio_bridge("start") # Give music back
                        wake_engine.start() 
                        continue
                
                try:
                    # 1️⃣ --- THE WAKE SOUND ---
                    play_sfx(config["audio"]["sfx_wake"])

                    # 2️⃣ --- THE AI TAKEOVER ---
                    start_ai_session(wake_engine, conn_manager, current_noise_floor)
                    
                    # 3️⃣ --- THE BLUETOOTH RESUME ---
                    print("✅ Session ended. Resuming media...")
                    manage_audio_bridge("start") # Give speakers back to Bluetooth
                    time.sleep(1) # Let the bridge initialize
                    threading.Thread(target=resume_media, daemon=True).start()
                    
                    # Reset OS back to idle
                    wake_engine.start()
                    time.sleep(0.5)   
                    print("\n✅ VOLCO OS READY | Waiting for wake word or button...")
                    
                except Exception as e:
                    print(f"⚠️ Connection lost during session. Resetting...")
                    conn_manager.close()
                    time.sleep(1)
                    manage_audio_bridge("start") # Give music back
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