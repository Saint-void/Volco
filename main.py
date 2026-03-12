import time
import platform
import sys
import threading

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
from core.bluetooth_pairing import enable_bluetooth_pairing 
from modes.ai_mode.session import start_ai_session
from modes.bt_mode.media_control import pause_media, resume_media
# ==========================================
# 🔘 HARDWARE BUTTON (GPIO)
# ==========================================
IS_WINDOWS = platform.system() == "Windows"
_button_pressed_event = False

if not IS_WINDOWS:
    try:
        import RPi.GPIO as GPIO
        
        BUTTON_PIN = 17 # ⚠️ Most Audio HAT buttons are on Pin 17. Change if needed!
        
        # Setup the GPIO board
        GPIO.setmode(GPIO.BCM)
        # We use an internal pull-up resistor. The button will pull it DOWN when pressed.
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        def button_callback(channel):
            global _button_pressed_event
            _button_pressed_event = True
            
        # Tell Linux to interrupt us ONLY when the button is physically pushed down (FALLING)
        # We add a 300ms "bouncetime" so a slightly jiggly button press doesn't trigger it 5 times.
        GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=300)
        print("🔘 [HARDWARE] Physical HAT button initialized on GPIO 17!")
        
    except ImportError:
        print("⚠️ [HARDWARE] RPi.GPIO not found! Button disabled.")
        
def check_for_button():
    """Checks the physical hardware state."""
    if IS_WINDOWS:
        return False # Ignore buttons if we are testing on a Windows PC
        
    global _button_pressed_event
    if _button_pressed_event:
        _button_pressed_event = False # Reset the trigger!
        return True
    return False

# =============================
# 🚀 THE DISPATCHER (MAIN OS)
# =============================
def main():
    # We removed the boot sound from here because it already played!
    
    # ⚡ 1. Initialize the Connection Manager FIRST
    conn_manager = ConnectionManager()
    
    # ⚡ 2. START BLUETOOTH & Pass the manager to the pipe!
    enable_bluetooth_pairing()
    start_data_pipe(conn_manager)

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
                        play_sfx(config["audio"]["sfx_offline"])
                        wake_engine.start() # Turn the mic back on so they can try again
                        continue
                
                try:
                    # 1️⃣ --- THE BLUETOOTH HIJACK (Instant Background Thread) ---
                    threading.Thread(target=pause_media, daemon=True).start()
                    play_sfx(config["audio"]["sfx_wake"])

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
        play_sfx("./assets/sounds/shutdown.wav")
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