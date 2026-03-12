import time
import platform
import sys
import threading
import subprocess # ⚡ Added to manage the Bluetooth audio bridge!

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
# 🎵 BLUETOOTH BRIDGE MANAGER
# ==========================================
def manage_audio_bridge(action="stop"):
    """Frees up the physical speakers for Vella, then gives them back to Bluetooth."""
    if action == "stop":
        # Kill the bridge to unlock the ALSA hardware
        subprocess.run(["killall", "bluealsa-aplay"], stderr=subprocess.DEVNULL)
    elif action == "start":
        # Restart the bridge in the background silently
        subprocess.Popen(["bluealsa-aplay", "00:00:00:00:00:00"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ==========================================
# 🔘 HARDWARE BUTTON (MODERN GPIOZERO)
# ==========================================
IS_WINDOWS = platform.system() == "Windows"
_button_pressed_event = False

if not IS_WINDOWS:
    try:
        from gpiozero import Button
        
        # We matched the 0.1s bounce_time from your successful test script
        volco_button = Button(17, bounce_time=0.1)
        
        def button_callback():
            global _button_pressed_event
            print("\n🚨 [HARDWARE INTERRUPT] Button was physically pressed!")
            _button_pressed_event = True
            
            # ⚡ INSTANT UNLOCK: Pause phone and kill bridge so the main loop unfreezes!
            threading.Thread(target=pause_media, daemon=True).start()
            manage_audio_bridge("stop")
            
        # Bind the hardware interrupt to our function
        volco_button.when_pressed = button_callback
        print("🔘 [HARDWARE] Physical HAT button initialized on GPIO 17!")
        
    except ImportError:
        print("⚠️ [HARDWARE] gpiozero not found! Button disabled.")
        
def check_for_button():
    """Checks the physical hardware state."""
    if IS_WINDOWS:
        return False 
        
    global _button_pressed_event
    
    # Failsafe: Also check if it's actively being held down, just in case!
    is_held_down = False
    try:
        is_held_down = volco_button.is_pressed
    except:
        pass
        
    if _button_pressed_event or is_held_down:
        _button_pressed_event = False # Reset the trigger!
        return True
        
    return False

# =============================
# 🚀 THE DISPATCHER (MAIN OS)
# =============================
def main():
    # ⚡ 1. Initialize the Connection Manager FIRST
    conn_manager = ConnectionManager()
    
    # ⚡ 2. START BLUETOOTH & Pass the manager to the pipe!
    enable_bluetooth_pairing()
    start_data_pipe(conn_manager)

    # ⚡ 3. Start the audio bridge automatically so music works on boot!
    manage_audio_bridge("start")

    # ⚡ 4. Load the Wake Engine
    wake_engine = WakeWordEngine()
    
    # ⚡ 5. Attempt Connection
    conn_manager.connect()

    # ⚡ 6. Calibrate the microphone
    current_noise_floor = calibrate_mic(duration=1.0)    
    
    try:
        wake_engine.start()
            
        while True:
            # Heartbeat
            conn_manager.send_ping()
            
            # 🎧 Listen for Wake Word (Will pause here if music is playing)
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