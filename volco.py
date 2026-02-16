import os
import time
import struct
import keyboard
import pyaudio
import pvporcupine
from pvrecorder import PvRecorder
import websocket # pip install websocket-client

# =============================
# CONFIGURATION
# =============================
# IMPORTANT: Use 'ws://' for WebSockets, not 'http://'
# Replace with your Server IP
# UPDATE THIS LINE
# We add ?client_type=device&user_id=sogolo
WS_URL = "ws://localhost:8001/volco_ws?client_type=device&user_id=sogolo"

PICOVOICE_ACCESS_KEY = "Sl361++BBZqn4rQXFqhoMICzrkMMg13QUDhlBU73myt6WcR93sbZMg==" 
PUSH_TO_TALK_KEY = "right shift"
CUSTOM_WAKE_WORD_PATH = "./assets/Hey-Vella_en_windows_v4_0_0.ppn" 

# Audio Settings
REC_FORMAT = pyaudio.paInt16
REC_CHANNELS = 1
REC_RATE = 16000
CHUNK = 512
SILENCE_THRESHOLD = 100
SILENCE_LIMIT = 0.7   

def handle_stream_transaction(trigger_source):
    """
    Handles the full bi-directional stream:
    1. Connect to WebSocket
    2. Stream Mic -> Server (Chunk by Chunk)
    3. Signal End of Speech ("COMMIT")
    4. Stream Server -> Speakers (Chunk by Chunk)
    """
    print(f"Connecting to {WS_URL}...")
    try:
        ws = websocket.create_connection(WS_URL)
    except Exception as e:
        print(f"Connection Error: {e}")
        return

    p = pyaudio.PyAudio()
    
    # --- PHASE 1: STREAMING INPUT (Mic -> Server) ---
    # We open the mic and send data AS we read it. No saving to file.
    mic_stream = p.open(
        format=REC_FORMAT, 
        channels=REC_CHANNELS, 
        rate=REC_RATE, 
        input=True, 
        frames_per_buffer=CHUNK
    )
    
    print("Streaming to Brain...")
    
    silence_start = None
    started_talking = False
    
    try:
        while True:
            # 1. Read Mic Data
            data = mic_stream.read(CHUNK, exception_on_overflow=False)
            
            # 2. Send to Server INSTANTLY
            ws.send_binary(data)
            
            # 3. Check Stop Condition (Button or Silence)
            if trigger_source == "PTT":
                if not keyboard.is_pressed(PUSH_TO_TALK_KEY):
                    break # User released button
            else: 
                # Auto-Silence Detection
                audio_data = struct.unpack_from("%dh" % CHUNK, data)
                if max(audio_data) > SILENCE_THRESHOLD:
                    started_talking = True
                    silence_start = None
                elif started_talking:
                    if silence_start is None: 
                        silence_start = time.time()
                    elif time.time() - silence_start > SILENCE_LIMIT: 
                        break # Silence limit reached
                    
    finally:
        mic_stream.stop_stream()
        mic_stream.close()
        
        # 4. Tell Server we are done talking
        print("Sending COMMIT signal...")
        ws.send("COMMIT")

    # --- PHASE 2: STREAMING OUTPUT (Server -> Speakers) ---
    print("Vella Speaking...")
    
    # Piper Output Stream (Usually 22050Hz)
    speaker_stream = p.open(
        format=pyaudio.paInt16, 
        channels=1, 
        rate=22050, 
        output=True
    )
    
    try:
        while True:
            # Receive Data from WebSocket
            # opcode 2 = Binary (Audio), opcode 1 = Text (Control signals)
            opcode, data = ws.recv_data()
            
            if opcode == websocket.ABNF.OPCODE_BINARY:
                # It's Audio -> Play Immediately
                speaker_stream.write(data)
                
            elif opcode == websocket.ABNF.OPCODE_TEXT:
                # It's a Control Signal
                msg = data.decode('utf-8')
                if msg == "END_OF_RESPONSE":
                    break
                elif msg == "NO_SPEECH":
                    print(" ⚠️ No speech detected.")
                    break
                    
    except Exception as e:
        print(f"Receive Error: {e}")
    finally:
        ws.close()
        speaker_stream.stop_stream()
        speaker_stream.close()
        p.terminate()
        print("Done.")

def main():
    porcupine = None
    recorder = None
    try:
        porcupine = pvporcupine.create(access_key=PICOVOICE_ACCESS_KEY, keyword_paths=[CUSTOM_WAKE_WORD_PATH])
        recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
        recorder.start()
        print("\n VELLA INPUT STREAMING ACTIVE")
        print(f"   - URL: {WS_URL}")
        
        while True:
            pcm = recorder.read()
            
            if keyboard.is_pressed(PUSH_TO_TALK_KEY):
                recorder.stop()
                # Pass "PTT" so it knows to wait for button release
                handle_stream_transaction("PTT")
                
                print("Resetting...")
                time.sleep(0.5)
                recorder.start()
                
            elif porcupine.process(pcm) >= 0:
                print("\n⚡ Hey Vella!")
                recorder.stop()
                # Pass "AUTO" so it uses silence detection
                handle_stream_transaction("AUTO")
                
                print("Resetting...")
                time.sleep(0.5)
                recorder.start()

    except KeyboardInterrupt:
        print("\n Shutdown.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if recorder is not None: recorder.delete()
        if porcupine is not None: porcupine.delete()

if __name__ == "__main__":
    while True:
        try:
            main()
        except BaseException:
            print("Restarting...")
            time.sleep(2)