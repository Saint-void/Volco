import json
import wave
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
import string
import subprocess

# Initialize the engine once
spotify = VolcoSpotifyEngine()
button_pressed_flag = threading.Event()

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
    
    # ❌ REMOVED: time.sleep(2) - We want lightning-fast response!
    
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

                print("🧠 Vella is processing... (Waiting for response)")

                # ⚡ Spotify volume was already ducked to 15% in main.py
                # No need to explicitly unmute/pause here to allow co-playing.

                # ⚡ THE INSTANT-KILL AUDIO LOOPER
                thinking_event = threading.Event()
                thinking_event.set()

                device_id = config["audio"].get("output_device_index") 

                def loading_sound_worker():
                    import wave
                    try:
                        wf = wave.open("./assets/sounds/ai_respond_loading.wav", 'rb')
                        # Open a dedicated stream just for the loading sound
                        load_stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                                             channels=wf.getnchannels(),
                                             rate=wf.getframerate(),
                                             output=True,
                                             output_device_index=device_id)
                        chunk_size = 1024
                        audio_data = wf.readframes(chunk_size)
                        
                        # Loop in tiny chunks so we can instantly abort
                        while thinking_event.is_set():
                            if len(audio_data) == 0:
                                wf.rewind() # Loop back to the beginning of the file
                                audio_data = wf.readframes(chunk_size)
                            load_stream.write(audio_data)
                            audio_data = wf.readframes(chunk_size)
                            
                        load_stream.stop_stream()
                        load_stream.close()
                    except Exception as e:
                        pass # Failsafe if file is missing

                # Start the loading sound in the background
                loading_thread = threading.Thread(target=loading_sound_worker, daemon=True)
                loading_thread.start()

                wake_engine.start()
                stop_event = threading.Event()

                # ⚡ BUTTON INTERRUPT WATCHER
                def watch_for_interrupt():
                    while not stop_event.is_set():
                        if button_pressed_flag.is_set():  
                            print("\n🛑 INTERRUPT (button)!")
                            conn_manager.send_data("INTERRUPT")
                            stop_event.set()
                            button_pressed_flag.clear() 
                        time.sleep(0.05) 

                t = threading.Thread(target=watch_for_interrupt, daemon=True)
                t.start()

                device_id = config["audio"].get("output_device_index")
                speaker_stream = p.open(format=pyaudio.paInt16, 
                                        channels=2, 
                                        rate=22050, 
                                        output=True,
                                        output_device_index=device_id   )

                voice_stream_active = True
                should_exit_to_wake_mode = False  
                first_response_received = False  # ⚡ Tracks when Vella actually replies

                while True:
                    if stop_event.is_set(): break
                    try:
                        opcode, data = conn_manager.recv_data()
                        if stop_event.is_set(): break

                        # ⚡ THE MOMENT VELLA REPLIES: Kill the sound & update the console
                        if not first_response_received:
                            first_response_received = True
                            thinking_event.clear() # This instantly stops the loading loop
                            print("🤖 Volco Speaking... (Press Button to Interrupt)")

                        if opcode == 2:  # Audio
                            if voice_stream_active:
                                stereo_data = audioop.tostereo(data, 2, 1, 1)
                                speaker_stream.write(stereo_data)

                        elif opcode == 1:  # Commands
                            msg = data
                            if isinstance(msg, str) and msg.startswith("{"):
                                try:
                                    payload = json.loads(msg)
                                    if payload.get("action"):
                                        should_exit_to_wake_mode = True

                                    if voice_stream_active:
                                        speaker_stream.stop_stream()
                                        speaker_stream.close()
                                        voice_stream_active = False
                                        print("🔇 Released ALSA for Spotify.")

                                    # Execute Spotify action
                                    query = payload.get("query", "").rstrip(".!?,")
                                    action = payload.get("action")
                                    if action == "spotify_play_track":
                                        spotify.search_and_play(query, "track")
                                    elif action == "spotify_next":
                                        spotify.control_playback("next")
                                    elif action == "spotify_previous":
                                        spotify.control_playback("previous")
                                    elif action == "spotify_pause":
                                        spotify.control_playback("pause")
                                    elif action == "spotify_resume":
                                        spotify.control_playback("resume")
                                    elif action == "spotify_play_album":
                                        spotify.search_and_play(query, "album")
                                    elif action == "spotify_play_playlist":
                                        spotify.search_and_play(query, "playlist")
                                    continue
                                except: pass

                            if msg == "END_OF_RESPONSE" or msg == "NO_SPEECH":
                                break

                    except Exception as e:
                        print(f"❌ Playback Error: {e}")
                        break

                # Cleanup
                stop_event.set()
                thinking_event.clear() # Failsafe to ensure sound loop dies
                t.join()
                wake_engine.stop()
                if voice_stream_active:
                    speaker_stream.close()

                if should_exit_to_wake_mode:
                    print("\n🎵 Music mode active. Returning to Wake Word listener...")
                    return

                print("\n👂 Ready for next turn...")

    except Exception as e:
        print(f"⚠️ Session Error: {e}")
        try: wake_engine.stop()
        except: pass
    finally:
        p.terminate()