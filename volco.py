import os
import time
import struct
import wave
import keyboard
import requests
import pyaudio
import pvporcupine
import winsound  # Native Windows Audio
from pvrecorder import PvRecorder

# =============================
# CONFIGURATION
# =============================
SERVER_URL = "https://exhilaratingly-heaveless-lael.ngrok-free.dev/volco_process"
PICOVOICE_ACCESS_KEY = "Sl361++BBZqn4rQXFqhoMICzrkMMg13QUDhlBU73myt6WcR93sbZMg==" 
PUSH_TO_TALK_KEY = "right shift"
CUSTOM_WAKE_WORD_PATH = "./assets/Hey-Vella_en_windows_v4_0_0.ppn" 

# Audio Settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
SILENCE_THRESHOLD = 500  
SILENCE_LIMIT = 1.0

def play_audio(file_path):
    """Plays WAV using native Windows drivers. Blocks by default."""
    if not os.path.exists(file_path):
        print("⚠️ Audio file missing.")
        return
    
    print("   ▶️ Playing audio...")
    try:
        # FIX: Removed invalid SND_WAIT. It waits by default.
        winsound.PlaySound(file_path, winsound.SND_FILENAME)
    except Exception as e:
        print(f"   ⚠️ Audio Playback Failed: {e}")
    print("   ⏹️ Audio finished.")

def record_audio_manual():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    frames = []
    print(" 🎤 [PTT] Recording...")
    try:
        while keyboard.is_pressed(PUSH_TO_TALK_KEY):
            frames.append(stream.read(CHUNK))
    finally:
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
    
    try:
        while True:
            data = stream.read(CHUNK)
            frames.append(data)
            audio_data = struct.unpack_from("%dh" % CHUNK, data)
            
            if max(audio_data) > SILENCE_THRESHOLD:
                started_talking = True
                silence_start = None
            elif started_talking:
                if silence_start is None: 
                    silence_start = time.time()
                elif time.time() - silence_start > SILENCE_LIMIT: 
                    break
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
    return frames

def save_and_send(frames):
    filename = "temp_input.wav"
    try:
        wf = wave.open(filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
    except Exception as e:
        print(f"❌ File Save Error: {e}")
        return

    print(" 🚀 Sending to Volco...")
    try:
        # 60s timeout for safety
        with open(filename, "rb") as f:
            response = requests.post(SERVER_URL, files={"audio": f}, timeout=60) 
        
        if response.status_code == 200:
            print(" 🤖 Vella is replying...")
            with open("reply.wav", "wb") as f:
                f.write(response.content)
            
            # Play using fixed function
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
        recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
        recorder.start()
        
        print("\n✅ VELLA SYSTEM ACTIVE")
        print(f"   - Say 'HEY VELLA' or hold '{PUSH_TO_TALK_KEY.upper()}'")

        while True:
            pcm = recorder.read()

            # 1. Push-to-Talk Check
            if keyboard.is_pressed(PUSH_TO_TALK_KEY):
                print("\n🎤 Push-to-talk active")
                recorder.stop()
                frames = record_audio_manual()
                save_and_send(frames)
                
                print("🔄 Resetting Ears...")
                time.sleep(0.5) 
                recorder.start()
                continue

            # 2. Wake Word Check
            if porcupine.process(pcm) >= 0:
                print("\n⚡ Wake word detected: Hey Vella")
                recorder.stop()
                frames = record_audio_auto()
                save_and_send(frames)
                
                print("🔄 Resetting Ears...")
                time.sleep(0.5)
                recorder.start()

    except KeyboardInterrupt:
        print("\n👋 User stopped script.")
        raise 
    except Exception as e:
        print(f"❌ Main Loop Logic Error: {e}")
    finally:
        if recorder is not None: recorder.delete()
        if porcupine is not None: porcupine.delete()

def run_forever():
    """Restarts the main function if it crashes."""
    while True:
        try:
            main()
        except KeyboardInterrupt:
            print("\nShutting down.")
            break
        except BaseException as e: 
            print(f"\n⚠️ CRITICAL CRASH DETECTED: {e}")
            print("♻️  Restarting Vella in 2 seconds...")
            time.sleep(2)

if __name__ == "__main__":
    run_forever()