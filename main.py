import time
import struct
import keyboard
import pyaudio
import threading
import websocket
from config.config_manager import config
from core.audio_io import play_sfx, print_audio_meter, calibrate_mic
from core.wake_word import WakeWordEngine
from core.connection import ConnectionManager

# =============================
# 📡 CONTINUOUS SESSION LOGIC
# =============================
def handle_continuous_session(wake_engine, conn_manager, noise_floor):
    """Handles the active listening and speaking phase after wake word."""
    p = pyaudio.PyAudio()
    
    # Audio config shortcuts
    chunk = config["audio"]["chunk"]
    rate = config["audio"]["rate"]
    channels = config["audio"]["channels"]
    dynamic_threshold = noise_floor + config["audio"]["safety_margin"]
    
    print(f"\n🧠 Adaptive Threshold set to: {dynamic_threshold}")

    try:
        while conn_manager.is_connected():
            # --- PHASE 1: LISTEN ---
            mic_stream = p.open(format=pyaudio.paInt16, channels=channels, rate=rate, input=True, frames_per_buffer=chunk)
            silence_start = None
            started_talking = False
            session_timer = time.time()
            speech_start_time = 0 
            valid_speech = False

            while True:
                data = mic_stream.read(chunk, exception_on_overflow=False)
                
                # Stream raw audio to server
                if not conn_manager.send_data(data):
                    break # Connection died
                
                volume = max(struct.unpack_from("%dh" % chunk, data))
                is_loud = volume > dynamic_threshold
                status = "RECORDING" if started_talking else "LISTENING"
                
                print_audio_meter(volume, dynamic_threshold, is_loud or started_talking, status)

                # Silence & Speech Detection Logic
                if is_loud:
                    if not started_talking:
                        started_talking = True
                        speech_start_time = time.time()
                    silence_start = None 
                    session_timer = time.time()
                elif started_talking:
                    if silence_start is None: silence_start = time.time()
                    total_speech_time = silence_start - speech_start_time
                    
                    if time.time() - silence_start > config["audio"]["silence_limit"]:
                        if total_speech_time > config["audio"]["min_speech_duration"]:
                            valid_speech = True
                            print(f"\n✅ Speech captured ({total_speech_time:.2f}s)")
                        else:
                            print(f"\n❌ Ignored noise ({total_speech_time:.2f}s)")
                            valid_speech = False
                        break 
                else:
                    if time.time() - session_timer > config["audio"]["session_timeout"]:
                        print("\n💤 Session Timeout.")
                        play_sfx(config["audio"]["sfx_sleep"])
                        mic_stream.stop_stream()
                        mic_stream.close()
                        return # Exit session, return to Idle 

            mic_stream.stop_stream()
            mic_stream.close()

            if not conn_manager.is_connected(): return

            # --- PHASE 2: SPEAK (TTS & INTERRUPT WATCHER) ---
            if valid_speech:
                print("🚀 Sending COMMIT...")
                if not conn_manager.send_data("COMMIT"): return

                print("🤖 Volco Speaking... (Say 'Hey Vella' to Interrupt)")
                
                wake_engine.start() # Restart wake word listener for interrupts
                stop_event = threading.Event()
                
                def watch_for_interrupt():
                    while not stop_event.is_set():
                        is_detected, _ = wake_engine.read_and_process()
                        if is_detected:
                            print("\n🛑 INTERRUPT TRIGGERED (Voice)!")
                            stop_event.set()
                        if keyboard.is_pressed("right shift"): # Configurable PTT key
                            print("\n🛑 INTERRUPT TRIGGERED (Button)!")
                            stop_event.set()

                t = threading.Thread(target=watch_for_interrupt)
                t.start()

                speaker_stream = p.open(format=pyaudio.paInt16, channels=1, rate=22050, output=True)
                
                while True:
                    if stop_event.is_set(): break
                    try:
                        opcode, data = conn_manager.recv_data()
                        if stop_event.is_set(): break
                        
                        if opcode == websocket.ABNF.OPCODE_BINARY:
                            speaker_stream.write(data)
                        elif opcode == websocket.ABNF.OPCODE_TEXT:
                            msg = data.decode('utf-8')
                            if msg == "END_OF_RESPONSE" or msg == "NO_SPEECH": 
                                break
                    except Exception:
                        conn_manager.set_offline() # Mark connection dead
                        break 
                
                # Cleanup turn
                stop_event.set()
                t.join()
                wake_engine.stop()
                speaker_stream.stop_stream()
                speaker_stream.close()
                
                if not conn_manager.is_connected(): return 
                print("\n👂 Ready for next turn...")
            else:
                print("🗑️ Ignored noise. Sending CLEAR to server...")
                conn_manager.send_data("CLEAR")


    except Exception as e:
        print(f"⚠️ Session Error: {e}")
        try: wake_engine.stop()
        except: pass
    finally:
        p.terminate()

# =============================
# 🚀 MAIN STATE MACHINE
# =============================
def main():
    # 1. Start Network Advertiser
    
    # 2. Initial Room Calibration
    print("\n--- VOLCO INITIALIZATION ---")
    current_noise_floor = calibrate_mic(duration=1.0)

    # 3. Load Engines
    wake_engine = WakeWordEngine()
    conn_manager = ConnectionManager()
    conn_manager.connect()

    print(f"\n✅ VOLCO V2 READY | Waiting for wake word...")
    
    try:
        wake_engine.start()
        
        while True:
            # 💓 Heartbeat & Reconnect Check
            conn_manager.send_ping()
            
            # 🎧 Listen for Wake Word
            is_wake_word, pcm = wake_engine.read_and_process()
            
            if is_wake_word:
                print("\n⚡ WAKE WORD DETECTED!")
                
                # ⚡ NEW: Force a real network test before we do anything
                if conn_manager.is_connected():
                    if not conn_manager.send_data("PING"):
                        print("🔌 Stale connection detected. Forcing reset...")
                        # This automatically sets conn_manager.ws to None
                
                # 1. Pre-flight check: Reconnect if socket dropped
                if not conn_manager.is_connected():
                    print("🔌 Connection lost. Attempting reconnect...")
                    if not conn_manager.connect():
                        print("❌ Failed to reconnect.")
                        play_sfx(config["audio"]["sfx_sleep"])
                        continue
                
                # 2. --- WAKE SEQUENCE ---
                try:
                    wake_engine.stop()

                    # Dive into conversation (uses the noise floor calculated at startup)
                    handle_continuous_session(wake_engine, conn_manager, current_noise_floor)
                    # Conversation ended, reset to idle
                    wake_engine.start()
                    print("\n✅ VOLCO V2 READY | Waiting for wake word...")
                    
                except Exception as e:
                    print(f"⚠️ Connection lost during session. Resetting...")
                    conn_manager.close()
                    time.sleep(1)
                    wake_engine.start()

    except KeyboardInterrupt:
        print("\n👋 Shutting down Volco...")
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