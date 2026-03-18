import json
import time
import struct
import pyaudio
import threading
import platform
import sys
import select
import audioop  # ⚡ NEW: Built-in audio operations library
from core.volco_audio_engine import VolcoSpotifyEngine
from config.config_manager import config
from core.audio_io import play_sfx, print_audio_meter

# Initialize the engine once
spotify = VolcoSpotifyEngine()

# ⚡ THE SMART OS CHECKER
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    import keyboard
else:
    import select

def is_button_pressed():
    """Checks for Space/Shift on Windows, or the 'Enter' key on Linux."""
    if IS_WINDOWS:
        return keyboard.is_pressed("space") or keyboard.is_pressed("right shift")  # type: ignore
    else:
        # Non-blocking check to see if 'Enter' was pressed in the Linux terminal
        i, _, _ = select.select([sys.stdin], [], [], 0.0)
        if i:
            sys.stdin.readline() # Clear the buffer
            return True
        return False

def start_ai_session(wake_engine, conn_manager, noise_floor):
    """Handles the active listening and speaking phase for Vella AI."""
    p = pyaudio.PyAudio()
    
    chunk = config["audio"]["chunk"]
    rate = config["audio"]["rate"]
    channels = config["audio"]["channels"]  
    dynamic_threshold = noise_floor + config["audio"]["safety_margin"]
    
    print(f"\n🧠 [AI MODE] Adaptive Threshold set to: {dynamic_threshold}")

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
                
                if not conn_manager.send_data(data):
                    break 
                
                volume = max(struct.unpack_from("%dh" % chunk, data))
                is_loud = volume > dynamic_threshold
                status = "RECORDING" if started_talking else "LISTENING"
                
                print_audio_meter(volume, dynamic_threshold, is_loud or started_talking, status)

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
                        play_sfx(config["audio"]["session_end"], async_play=True)
                        mic_stream.stop_stream()
                        mic_stream.close()
                        return 

            mic_stream.stop_stream()
            mic_stream.close()

            if not conn_manager.is_connected(): return

            # --- PHASE 2: SPEAK ---
            if valid_speech:
                print("🚀 Sending COMMIT...")
                if not conn_manager.send_data("COMMIT"): return

                print("🤖 Volco Speaking... (Press 'Enter' to Interrupt)")
                
                wake_engine.start() 
                stop_event = threading.Event()
                
                def watch_for_interrupt():
                    while not stop_event.is_set():
                        is_detected, _ = wake_engine.read_and_process()
                        if is_detected:
                            print("\n🛑 INTERRUPT TRIGGERED (Voice)!")
                            stop_event.set()
                        # ⚡ UPDATED: Using our smart OS checker instead of strict keyboard!
                        if is_button_pressed(): 
                            print("\n🛑 INTERRUPT TRIGGERED (Button)!")
                            stop_event.set()

                t = threading.Thread(target=watch_for_interrupt)
                t.start()

                device_id = config["audio"].get("output_device_index")
               # ⚡ FIX 1: Change channels from 1 to 2 to satisfy the Waveshare HAT
                speaker_stream = p.open(format=pyaudio.paInt16, 
                                        channels=2, 
                                        rate=22050, 
                                        output=True)
                
                while True:
                    if stop_event.is_set(): break
                    try:
                        opcode, data = conn_manager.recv_data()
                        if stop_event.is_set(): break
                        
                        # ⚡ UDP AUDIO CHUNKS (Opcode 2)
                        if opcode == 2: 
                            # ⚡ FIX 2: Convert Mono to Stereo on the fly
                            # audioop.tostereo(data, byte_width, left_volume, right_volume)
                            stereo_data = audioop.tostereo(data, 2, 1, 1)
                            speaker_stream.write(stereo_data)
                            
                        # ⚡ UDP TEXT COMMANDS (Opcode 1)
                        elif opcode == 1: 
                            msg = data 
                            
                            # --- 🎵 SPOTIFY COMMAND CHECK ---
                            try:
                                payload = json.loads(msg)
                                action = payload.get("action")
                                query = payload.get("query")
                                
                                if action:
                                    print(f"🎵 Executing Spotify Action: {action}")
                                    if action == "spotify_resume": spotify.play_resume()
                                    elif action == "spotify_pause": spotify.pause()
                                    elif action == "spotify_next": spotify.next_track()
                                    elif action == "spotify_previous": spotify.previous_track()
                                    elif action == "spotify_play_track": spotify.search_and_play(query, "track")
                                    elif action == "spotify_play_album": spotify.search_and_play(query, "album")
                                    elif action == "spotify_play_playlist": spotify.search_and_play(query, "playlist")
                                    # Since it was a command, we can skip the rest of the loop
                                    continue 
                            except:
                                # Not JSON? No problem, just treat it as a normal string
                                pass

                            if msg == "END_OF_RESPONSE" or msg == "NO_SPEECH": 
                                break
                                
                    except Exception as e:
                        print(f"\n❌ [PLAYBACK ERROR] {e}")
                        conn_manager.set_offline(f"Playback Error: {e}") 
                        break
                
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