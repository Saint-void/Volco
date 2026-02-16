import os
import time
import struct
import keyboard
import pyaudio
import pvporcupine
from pvrecorder import PvRecorder
import websocket # pip install websocket-client
import sys

# =============================
# CONFIGURATION
# =============================
WS_URL = "ws://localhost:8001/volco_ws?client_type=device&user_id=sogolo"

PICOVOICE_ACCESS_KEY = "Sl361++BBZqn4rQXFqhoMICzrkMMg13QUDhlBU73myt6WcR93sbZMg==" 
PUSH_TO_TALK_KEY = "right shift"
CUSTOM_WAKE_WORD_PATH = "./assets/Hey-Vella_en_windows_v4_0_0.ppn" 

# Audio Settings
REC_FORMAT = pyaudio.paInt16
REC_CHANNELS = 1
REC_RATE = 16000
CHUNK = 512

# 🧠 ADAPTIVE SETTINGS
SILENCE_LIMIT = 1.0       # Wait 1.0s of silence to confirm end of sentence
SAFETY_MARGIN = 500       # INCREASED: Needs to be distinctly louder than room
SESSION_TIMEOUT = 5.0     # 5s of silence = Sleep
MIN_SPEECH_DURATION = 0.5 # 🛡️ IGNORE sounds shorter than this (clicks/coughs)

CURRENT_NOISE_FLOOR = 500 

# =============================
# 🛠️ HELPER: VISUALIZER
# =============================
def print_audio_meter(volume, threshold, is_active, status_text="LISTENING"):
    scaled_vol = int(volume / 400) 
    if scaled_vol > 20: scaled_vol = 20
    bar = "█" * scaled_vol + "-" * (20 - scaled_vol)
    color = "\033[92m" if is_active else "\033[90m"
    reset = "\033[0m"
    sys.stdout.write(f"\r{color}🎤 {status_text} | Level: {volume:05d} | Trig: {threshold} | [{bar}]{reset}")
    sys.stdout.flush()

# =============================
# 🛠️ HELPER: CALIBRATE MIC
# =============================
def calibrate_mic():
    global CURRENT_NOISE_FLOOR
    p = pyaudio.PyAudio()
    stream = p.open(format=REC_FORMAT, channels=REC_CHANNELS, rate=REC_RATE, input=True, frames_per_buffer=CHUNK)
    print("\n🤫 Measuring room noise...")
    max_noise = 0
    start = time.time()
    while time.time() - start < 1.0:
        data = stream.read(CHUNK, exception_on_overflow=False)
        peak = max(struct.unpack_from("%dh" % CHUNK, data))
        if peak > max_noise: max_noise = peak
        print_audio_meter(peak, 0, False, "CALIBRATING")
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    CURRENT_NOISE_FLOOR = max_noise
    print(f"\n✅ Noise Floor: {CURRENT_NOISE_FLOOR} | Trig: {CURRENT_NOISE_FLOOR + SAFETY_MARGIN}\n")

# =============================
# 📡 CONTINUOUS SESSION LOGIC
# =============================
def handle_continuous_session():
    print(f"🔌 Connecting to Brain...")
    try:
        ws = websocket.create_connection(WS_URL)
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    p = pyaudio.PyAudio()
    DYNAMIC_THRESHOLD = CURRENT_NOISE_FLOOR + SAFETY_MARGIN
    
    try:
        while True:
            # --- PHASE 1: LISTEN ---
            mic_stream = p.open(format=REC_FORMAT, channels=REC_CHANNELS, rate=REC_RATE, input=True, frames_per_buffer=CHUNK)
            
            silence_start = None
            started_talking = False
            session_timer = time.time()
            speech_start_time = 0 # Track when you STARTED talking
            valid_speech = False # Only true if you talk long enough

            while True:
                data = mic_stream.read(CHUNK, exception_on_overflow=False)
                ws.send_binary(data)
                
                volume = max(struct.unpack_from("%dh" % CHUNK, data))
                is_loud = volume > DYNAMIC_THRESHOLD
                
                status = "RECORDING" if started_talking else "LISTENING"
                print_audio_meter(volume, DYNAMIC_THRESHOLD, is_loud or started_talking, status)

                # 1. USER IS SPEAKING
                if is_loud:
                    if not started_talking:
                        started_talking = True
                        speech_start_time = time.time() # Start the stopwatch
                    
                    silence_start = None 
                    session_timer = time.time()
                
                # 2. USER STOPPED SPEAKING
                elif started_talking:
                    if silence_start is None: 
                        silence_start = time.time()
                    
                    # Check duration of the speech block
                    total_speech_time = silence_start - speech_start_time

                    if time.time() - silence_start > SILENCE_LIMIT:
                        # SENTENCE FINISHED. Was it long enough?
                        if total_speech_time > MIN_SPEECH_DURATION:
                            valid_speech = True
                            print(f"\n✅ Speech captured ({total_speech_time:.2f}s)")
                        else:
                            print(f"\n❌ Ignored noise ({total_speech_time:.2f}s)")
                            valid_speech = False
                        
                        break # BREAK INNER LOOP
                
                # 3. TIMEOUT (Pure Silence)
                else:
                    if time.time() - session_timer > SESSION_TIMEOUT:
                        print("\n💤 Session Timeout. Going to sleep.")
                        mic_stream.stop_stream()
                        mic_stream.close()
                        ws.close()
                        p.terminate()
                        return 

            # --- END OF LISTENING PHASE ---
            mic_stream.stop_stream()
            mic_stream.close()
            
            if valid_speech:
                print("🚀 Sending COMMIT...")
                ws.send("COMMIT")

                # --- PHASE 2: SPEAK ---
                print("🤖 Volco Speaking...")
                speaker_stream = p.open(format=pyaudio.paInt16, channels=1, rate=22050, output=True)
                
                while True:
                    try:
                        opcode, data = ws.recv_data()
                        if opcode == websocket.ABNF.OPCODE_BINARY:
                            speaker_stream.write(data)
                        elif opcode == websocket.ABNF.OPCODE_TEXT:
                            msg = data.decode('utf-8')
                            if msg == "END_OF_RESPONSE": break
                            elif msg == "NO_SPEECH": break
                    except: break
                
                speaker_stream.stop_stream()
                speaker_stream.close()
                print("\n👂 Ready for next turn...")
            
            else:
                # If it was just noise, DON'T commit. Just reset buffer.
                # Sending a dummy "RESET" or just sending empty audio logic implies
                # we just loop back and wait for REAL speech.
                pass
            
    except Exception as e:
        print(f"\n❌ Session Error: {e}")
    finally:
        try: ws.close()
        except: pass
        p.terminate()

# =============================
# 🚀 MAIN LOOP
# =============================
def main():
    calibrate_mic()

    porcupine = None
    recorder = None
    try:
        porcupine = pvporcupine.create(access_key=PICOVOICE_ACCESS_KEY, keyword_paths=[CUSTOM_WAKE_WORD_PATH])
        recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
        recorder.start()
        print(f"✅ VOLCO READY | Waiting for 'Hey Vella'...")
        
        while True:
            pcm = recorder.read()
            if porcupine.process(pcm) >= 0:
                print("\n⚡ WAKE WORD DETECTED!")
                recorder.stop()
                handle_continuous_session()
                print("\n✅ VOLCO READY | Waiting for 'Hey Vella'...")
                recorder.start()

    except KeyboardInterrupt:
        print("\n👋 Goodbye.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if recorder is not None: recorder.delete()
        if porcupine is not None: porcupine.delete()

if __name__ == "__main__":
    while True:
        try: main()
        except BaseException as e:
            print(f"Restarting... {e}")
            time.sleep(2)