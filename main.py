import time
import sys
import threading

# ⚡ 1. ONLY IMPORT THE AUDIO ENGINE FIRST
from core.audio_io import play_sfx

# ⚡ 2. PLAY THE BOOT SOUND INSTANTLY!
print("\n--- VOLCO OS INITIALIZING ---")

# ⚡ 3. NOW LOAD THE HEAVY AI LIBRARIES IN THE BACKGROUND
from config.config_manager import config
from core.audio_io import calibrate_mic
from core.wake_word import WakeWordEngine
from core.connection import ConnectionManager
from core.data_pipe import start_data_pipe
from core.volco_spotify import VolcoSpotifyManager

play_sfx("./assets/sounds/boot.wav")

from core.bluetooth_pairing import enable_bluetooth_pairing, set_bluetooth_power
from core.platform_support import (
    can_use_bluealsa_bridge,
    can_use_gpio_button,
    is_macos,
    platform_label,
    popen_quiet,
    run_quiet,
)
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
_audio_bridge_skip_logged = False


def manage_audio_bridge(action="stop"):
    global _audio_bridge_skip_logged

    if not can_use_bluealsa_bridge():
        if action == "start" and not _audio_bridge_skip_logged:
            print(f"🎵 [AUDIO BRIDGE] BlueALSA bridge skipped on {platform_label()}.")
            _audio_bridge_skip_logged = True
        return False

    run_quiet(["killall", "bluealsa-aplay"])
    if action == "start":
        popen_quiet(["bluealsa-aplay", "00:00:00:00:00:00"])
    return True

# ==========================================
# 🔘 GLOBAL STATE & MANAGERS
# ==========================================
# Power State Trackers
volco_sleeping = False
ai_session_active = False
_was_held_flag = False
conn_manager = None
volco_button = None

# New Trigger Events for the threaded engine
trigger_event = threading.Event()
trigger_type = "VOICE"

# ==========================================
# 🔘 HARDWARE BUTTON INTERRUPTS
# ==========================================
def enter_sleep():
    """Shared sleep path for Pi button holds and laptop terminal controls."""
    global volco_sleeping

    if volco_sleeping:
        return

    print("\n🌙 [POWER] Entering Deep Sleep...")
    volco_sleeping = True
    threading.Thread(target=play_sfx, args=("./assets/sounds/shutdown.wav",), daemon=True).start()
    spotify_hw.stop_client()
    manage_audio_bridge("stop")
    set_bluetooth_power(False)


def wake_up():
    """Shared wake path for Pi button clicks and laptop terminal controls."""
    global volco_sleeping

    if not volco_sleeping:
        return

    print("\n☀️ [POWER] Waking up Volco!")
    volco_sleeping = False
    threading.Thread(target=play_sfx, args=("./assets/sounds/boot.wav",), daemon=True).start()
    time.sleep(2)

    if set_bluetooth_power(True):
        threading.Thread(target=play_sfx, args=("./assets/sounds/bt_pairing.wav",), daemon=True).start()

    print("🎵 [POWER] Starting Standalone Spotify Client...")
    spotify_hw.start_client()


def trigger_ai(source="BUTTON"):
    global trigger_type

    if volco_sleeping:
        wake_up()
        return

    if ai_session_active:
        print("\n🔘 [CONTROL] AI already active; trigger ignored.")
        return

    print(f"\n🚨 [CONTROL] {source} trigger! Starting AI...")
    trigger_type = source
    trigger_event.set()


def _start_terminal_controls():
    print("⌨️ [DEV INPUT] Press Enter to trigger AI. Type 'sleep' or 'wake' for power controls.")

    def terminal_worker():
        while True:
            try:
                line = sys.stdin.readline()
                if line == "":
                    return

                command = line.strip().lower()
                if command in {"sleep", "s"}:
                    enter_sleep()
                elif command in {"wake", "w"}:
                    wake_up()
                elif command in {"quit", "exit"}:
                    print("⌨️ [DEV INPUT] Use Ctrl-C to shut down Volco.")
                else:
                    trigger_ai("TERMINAL")
            except Exception as e:
                print(f"⚠️ [DEV INPUT] Listener stopped: {e}")
                return

    threading.Thread(target=terminal_worker, daemon=True).start()


def _setup_controls():
    global volco_button, _was_held_flag

    if can_use_gpio_button():
        try:
            from gpiozero import Button #type: ignore

            volco_button = Button(17, bounce_time=0.1, hold_time=3.0)

            def button_held():
                global _was_held_flag
                _was_held_flag = True
                enter_sleep()

            def button_released():
                global _was_held_flag

                if _was_held_flag:
                    _was_held_flag = False
                    return

                if volco_sleeping:
                    wake_up()
                else:
                    trigger_ai("BUTTON")

            volco_button.when_held = button_held
            volco_button.when_released = button_released
            print("🔘 [HARDWARE] Smart Button (Click/Hold) initialized on GPIO 17!")
            return

        except Exception as e:
            print(f"⚠️ [HARDWARE] GPIO button unavailable: {e}")

    if is_macos():
        print("🔘 [HARDWARE] MacBook mode active; GPIO button disabled.")
    else:
        print(f"🔘 [HARDWARE] GPIO button disabled on {platform_label()}.")
    _start_terminal_controls()


_setup_controls()


def wake_word_worker(wake_engine):
    """Background thread to listen for the wake word without blocking the OS."""
    global trigger_event, trigger_type, volco_sleeping, ai_session_active
    
    if not wake_engine.is_functional:
        print("❌ [WAKE THREAD] Engine not functional. Thread exiting.")
        return

    print("👂 [WAKE THREAD] Background listener active and waiting for audio...")
    
    while True:
        if volco_sleeping:
            time.sleep(0.5)
            continue

        if ai_session_active or trigger_event.is_set():
            time.sleep(0.05)
            continue

        # Wait for stream to be ready if it's not yet
        if wake_engine.audio_stream is None:
            time.sleep(0.1)
            continue

        is_wake, confidence = wake_engine.read_and_process()
        if is_wake and not ai_session_active and not trigger_event.is_set():
            print(f"🎯 [WAKE THREAD] Match found! Confidence: {confidence:.2f}")
            trigger_type = "VOICE"
            trigger_event.set()
            # 1 --- THE WAKE SOUND (Now Async!) ---
            play_sfx(config["audio"]["sfx_wake"], async_play=True)

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
    if conn_manager.connect():
        print("🧠 [DEBUG] Connected to server.")
    else:
        print("🧠 [DEBUG] Server connection pending; Volco will retry on trigger.")

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
                session_trigger_type = trigger_type
                print(f"\n⚡ WAKE TRIGGERED ({session_trigger_type})!")
                trigger_event.clear()
                ai_session_active = True

                # 🔉 Duck music in the background so the mic can open immediately.
                duck_target = 15
                duck_state = {"previous_volume": None, "ducked": False}
                duck_lock = threading.Lock()
                session_done = threading.Event()

                def duck_music_worker():
                    previous_volume = spotify_api.get_current_volume()
                    if session_done.is_set() or previous_volume is None or previous_volume <= duck_target:
                        return

                    with duck_lock:
                        duck_state["previous_volume"] = previous_volume
                        duck_state["ducked"] = True

                    spotify_api.fade_volume(target_volume=duck_target, start_volume=previous_volume)

                threading.Thread(target=duck_music_worker, daemon=True).start()
                wake_engine.stop() 
                wake_engine.reset_detection_state(suppress_seconds=1.0, require_rearm=True)
                
                # Network Check
                if not conn_manager.is_connected():
                    print("🔌 Connection lost. Attempting reconnect...")
                    if not conn_manager.connect():
                        print("❌ Failed to reconnect.")
                        session_done.set()
                        with duck_lock:
                            previous_volume = duck_state["previous_volume"]
                            ducked = duck_state["ducked"]
                        if ducked and previous_volume is not None:
                            spotify_api.fade_volume(target_volume=previous_volume, start_volume=duck_target)
                        trigger_event.clear()
                        ai_session_active = False
                        wake_engine.start() 
                        continue
                
                try:

                    # --- THE AI TAKEOVER ---
                    start_ai_session(wake_engine, conn_manager, current_noise_floor)
                    
                    session_done.set()
                    with duck_lock:
                        previous_volume = duck_state["previous_volume"]
                        ducked = duck_state["ducked"]
                    if ducked and previous_volume is not None:
                        print("✅ Session ended. Resuming media volume...")
                        spotify_api.fade_volume(target_volume=previous_volume, start_volume=duck_target)                   
                    
                    trigger_event.clear()
                    wake_engine.start()
                    time.sleep(0.5)   
                    print("\n✅ VOLCO OS READY | Waiting for wake word or button...")
                    
                except Exception as e:
                    print(f"⚠️ Error during session: {e}")
                    session_done.set()
                    with duck_lock:
                        previous_volume = duck_state["previous_volume"]
                        ducked = duck_state["ducked"]
                    if ducked and previous_volume is not None:
                        spotify_api.fade_volume(target_volume=previous_volume, start_volume=duck_target)
                    conn_manager.close()
                    trigger_event.clear()
                    wake_engine.reset_detection_state(suppress_seconds=1.0, require_rearm=True)
                    wake_engine.start()
                finally:
                    session_done.set()
                    ai_session_active = False
                    
    except KeyboardInterrupt:
        print("\n👋 Shutting down Volco OS...")
        manage_audio_bridge("stop")
        play_sfx("./assets/sounds/shutdown.wav")
    finally:
        ai_session_active = False
        trigger_event.clear()
        manage_audio_bridge("stop")
        conn_manager.close()
        wake_engine.cleanup()

if __name__ == "__main__":                                  
    while True:
        try:
            main()
            break
        except KeyboardInterrupt:
            print("\n👋 Shutting down Volco OS...")
            break
        except Exception as e:
            print(f"🔄 Hard Restart Triggered: {e}")
            time.sleep(2)
