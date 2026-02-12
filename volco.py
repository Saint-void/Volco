import os
import time
import struct
import wave
import keyboard
import requests
import pyaudio
import pvporcupine
import simpleaudio as sa
from pvrecorder import PvRecorder

# =============================
# CONFIGURATION
# =============================
SERVER_URL = "https://exhilaratingly-heaveless-lael.ngrok-free.dev/volco_process"
PICOVOICE_ACCESS_KEY = "Sl361++BBZqn4rQXFqhoMICzrkMMg13QUDhlBU73myt6WcR93sbZMg==" 
PUSH_TO_TALK_KEY = "right shift"

# Path to your custom Vella file
CUSTOM_WAKE_WORD_PATH = "./assets/Hey-Vella_en_windows_v4_0_0.ppn" 

# Audio Settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
SILENCE_THRESHOLD = 500  
SILENCE_LIMIT = 1      # Wait slightly longer for you to finish speaking

def play_audio(file_path):
    """Plays the WAV file and blocks until finished."""
    if not os.path.exists(file_path):
        return
    wave_obj = sa.WaveObject.from_wave_file(file_path)
    play_obj = wave_obj.play()
    play_obj.wait_done()  # 🛑 Crucial: Holds the script here until audio ends

def record_audio_manual():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    frames = []
    print(" 🎤 [PTT] Recording...")
    while keyboard.is_pressed(PUSH_TO_TALK_KEY):
        frames.append(stream.read(CHUNK))
    stream.stop_stream()
    stream.close()
    p.terminate()
    return frames

def record_audio_auto():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    frames = []
    print(" 🎤 [AUTO] Listening to you...")
    
    silence_start = None
    started_talking = False
    
    while True:
        data = stream.read(CHUNK)
        frames.append(data)
        audio_data = struct.unpack_from("%dh" % CHUNK, data)
        if max(audio_data) > SILENCE_THRESHOLD:
            started_talking = True
            silence_start = None
        elif started_talking:
            if silence_start is None: silence_start = time.time()
            elif time.time() - silence_start > SILENCE_LIMIT: break
            
    stream.stop_stream()
    stream.close()
    p.terminate()
    return frames

def save_and_send(frames):
    filename = "temp_input.wav"
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(2)
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    print(" 🚀 Sending to Volco...")
    try:
        with open(filename, "rb") as f:
            response = requests.post(SERVER_URL, files={"audio": f})
        
        if response.status_code == 200:
            print(" 🤖 Vella is replying...")
            with open("reply.wav", "wb") as f:
                f.write(response.content)
            play_audio("reply.wav")
        else:
            print(f" ❌ Server Error: {response.status_code}")
    except Exception as e:
        print(f" ❌ Connection Failed: {e}")

def main():
    porcupine = None
    recorder = None
    try:
        porcupine = pvporcupine.create(
            access_key=PICOVOICE_ACCESS_KEY,
            keyword_paths=[CUSTOM_WAKE_WORD_PATH]
        )

        recorder = PvRecorder(
            device_index=-1,
            frame_length=porcupine.frame_length
        )

        recorder.start()

    except Exception as e:
        print(f"❌ Init failed: {e}")
        if recorder is not None:
            recorder.delete()
        if porcupine is not None:
            porcupine.delete()
        raise

    print("\n✅ VELLA SYSTEM ACTIVE")
    print(f"   - Say 'HEY VELLA' or hold '{PUSH_TO_TALK_KEY.upper()}'")

    # ... inside main() ...
    print(f"\n✅ VELLA SYSTEM ACTIVE")
    print(f"   - Say 'HEY VELLA' or hold '{PUSH_TO_TALK_KEY.upper()}'")

    try:
        while True:
            pcm = recorder.read()

            # 1. Push-to-Talk Check
            if keyboard.is_pressed(PUSH_TO_TALK_KEY):
                print("\n🎤 Push-to-talk active")
                
                recorder.stop() # <--- CRITICAL FIX: Release Mic
                frames = record_audio_manual()
                save_and_send(frames)
                recorder.start() # <--- CRITICAL FIX: Re-take Mic
                
                print("\n🔄 Waiting for wake word...")
                continue

            # 2. Wake Word Check
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                print("\n⚡ Wake word detected: Hey Vella")
                
                recorder.stop() # <--- CRITICAL FIX
                frames = record_audio_auto()
                save_and_send(frames)
                recorder.start() # <--- CRITICAL FIX
                
                print("\n🔄 Waiting for wake word...")

    except KeyboardInterrupt:
        print("\n👋 Shutting down.")
        raise

    finally:
        recorder.delete()
        porcupine.delete()

                         
def run_forever():
    while True:
        try:
            main()
        except KeyboardInterrupt:
            print("\nShutting down.")
            break
        except Exception as e:
            print(f"Fatal error: {e}")
            print("Restarting in 2 seconds...")
            time.sleep(2)


if __name__ == "__main__":
    run_forever()
