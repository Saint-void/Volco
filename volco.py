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
# ⚠️ REPLACE WITH YOUR SERVER IP (Keep the user_id params)
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
SILENCE_LIMIT = 1.2  # Seconds of silence before sending
SAFETY_MARGIN = 300  # How much louder than room noise your voice must be

# Global variable to store the room noise level
CURRENT_NOISE_FLOOR = 500 

# =============================
# 🛠️ HELPER: VISUALIZER
# =============================
def print_audio_meter(volume, threshold, is_active):
    """
    Prints a cool retro volume bar to the terminal.
    """
    # Create a bar of 20 segments
    # Max expected volume is usually around 10,000 for normal speech
    scaled_vol = int(volume / 400) 
    if scaled_vol > 20: scaled_vol = 20
    
    bar = "█" * scaled_vol + "-" * (20 - scaled_vol)
    
    status = "🔴 ACTIVE" if is_active else "⚪ SILENT"
    color = "\033[92m" if is_active else "\033[90m" # Green if active, Gray if silent
    reset = "\033[0m"
    
    # \r overwrites the line
    sys.stdout.write(f"\r{color}🎤 {status} | Level: {volume:05d} | Trig: {threshold} | [{bar}]{reset}")
    sys.stdout.flush()

# =============================
# 🛠️ HELPER: CALIBRATE MIC
# =============================
def calibrate_mic():
    """
    Listens for 1 second to determine the background noise level.
    """
    global CURRENT_NOISE_FLOOR
    p = pyaudio.PyAudio()
    stream = p.open(format=REC_FORMAT, channels=REC_CHANNELS, rate=REC_RATE, input=True, frames_per_buffer=CHUNK)
    
    print("\n🤫 Sshhh! Measuring room noise for 1 second...")
    
    max_noise = 0
    start = time.time()
    
    while time.time() - start < 1.0:
        data = stream.read(CHUNK, exception_on_overflow=False)
        audio_data = struct.unpack_from("%dh" % CHUNK, data)
        peak = max(audio_data)
        if peak > max_noise:
            max_noise = peak
        
        # Show calibration live
        print_audio_meter(peak, 0, False)
            
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Set the floor. 
    CURRENT_NOISE_FLOOR = max_noise
    print(f"\n✅ Room Noise Floor: {CURRENT_NOISE_FLOOR}")
    print(f"🎯 Trigger Threshold: {CURRENT_NOISE_FLOOR + SAFETY_MARGIN}")
    print("--------------------------------------------------")

# =============================
# 📡 STREAMING LOGIC
# =============================
def handle_stream_transaction(trigger_source):
    print(f"\n🔌 Connecting to Brain...")
    try:
        ws = websocket.create_connection(WS_URL)
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    p = pyaudio.PyAudio()
    mic_stream = p.open(format=REC_FORMAT, channels=REC_CHANNELS, rate=REC_RATE, input=True, frames_per_buffer=CHUNK)
    
    print("🎤 Speak now...")
    
    silence_start = None
    started_talking = False
    
    # Calculate the dynamic threshold for THIS turn
    DYNAMIC_THRESHOLD = CURRENT_NOISE_FLOOR + SAFETY_MARGIN
    
    try:
        while True:
            # 1. Read Mic
            data = mic_stream.read(CHUNK, exception_on_overflow=False)
            ws.send_binary(data)
            
            # 2. PTT Logic
            if trigger_source == "PTT":
                if not keyboard.is_pressed(PUSH_TO_TALK_KEY):
                    break 
            
            # 3. Auto-Silence Logic
            else: 
                audio_data = struct.unpack_from("%dh" % CHUNK, data)
                volume_level = max(audio_data)
                
                # Check active status
                is_loud_enough = volume_level > DYNAMIC_THRESHOLD

                # VISUALIZE IT LIVE
                print_audio_meter(volume_level, DYNAMIC_THRESHOLD, is_loud_enough or started_talking)

                # If you are louder than the room + margin -> You are talking
                if is_loud_enough:
                    started_talking = True
                    silence_start = None # Reset silence timer
                
                # If you are quiet -> Start counting down
                elif started_talking:
                    if silence_start is None: 
                        silence_start = time.time()
                    elif time.time() - silence_start > SILENCE_LIMIT: 
                        print("\n🤐 Silence limit reached. Sending...")
                        break 
                    
    except Exception as e:
        print(f"\n❌ Mic Error: {e}")
    finally:
        mic_stream.stop_stream()
        mic_stream.close()
        ws.send("COMMIT")

    # --- SPEAKING PHASE ---
    print("\n🤖 Volco Thinking...")
    speaker_stream = p.open(format=pyaudio.paInt16, channels=1, rate=22050, output=True)
    
    try:
        while True:
            opcode, data = ws.recv_data()
            if opcode == websocket.ABNF.OPCODE_BINARY:
                speaker_stream.write(data)
            elif opcode == websocket.ABNF.OPCODE_TEXT:
                msg = data.decode('utf-8')
                if msg == "END_OF_RESPONSE": break
                elif msg == "NO_SPEECH": 
                    print("⚠️ Server heard silence.")
                    break
    except Exception as e:
        print(f"Playback Error: {e}")
    finally:
        ws.close()
        speaker_stream.stop_stream()
        speaker_stream.close()
        p.terminate()
        print("Done.\n")

# =============================
# 🚀 MAIN LOOP
# =============================
def main():
    # 1. Run Calibration once at startup
    calibrate_mic()

    porcupine = None
    recorder = None
    try:
        porcupine = pvporcupine.create(access_key=PICOVOICE_ACCESS_KEY, keyword_paths=[CUSTOM_WAKE_WORD_PATH])
        recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
        recorder.start()
        print(f"✅ VOLCO READY | URL: {WS_URL}")
        
        while True:
            pcm = recorder.read()
            
            if keyboard.is_pressed(PUSH_TO_TALK_KEY):
                recorder.stop()
                handle_stream_transaction("PTT")
                time.sleep(0.5)
                recorder.start()
                
            elif porcupine.process(pcm) >= 0:
                print("\n⚡ Hey Vella!")
                recorder.stop()
                handle_stream_transaction("AUTO")
                time.sleep(0.5)
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
        try:
            main()
        except BaseException as e:
            print(f"Restarting... {e}")
            time.sleep(2)