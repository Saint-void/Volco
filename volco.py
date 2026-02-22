import os
import time
import struct
import keyboard
import pyaudio
import wave
import pvporcupine
from pvrecorder import PvRecorder
import websocket
import sys
import socket
import threading
from zeroconf import ServiceInfo, Zeroconf

# =============================
# CONFIGURATION 
# =============================
# ⚠️ MAKE SURE THIS MATCHES YOUR NGROK
WS_URL = "wss://exhilaratingly-heaveless-lael.ngrok-free.dev/volco_ws?client_type=device&user_id=sogolo"

PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")
if PICOVOICE_ACCESS_KEY is None:
    raise ValueError("PICOVOICE_ACCESS_KEY is not set. Check your environment variables.")

PUSH_TO_TALK_KEY = "right shift"
CUSTOM_WAKE_WORD_PATH = "./assets/Hey-Vella_en_windows_v4_0_0.ppn" 

SFX_WAKE = "./assets/sounds/wake.wav"
SFX_SLEEP = "./assets/sounds/sleep.wav"

REC_FORMAT = pyaudio.paInt16
REC_CHANNELS = 1
REC_RATE = 16000
CHUNK = 512 

# FIXED: Added explicit playback rate so it isn't buried in the code.
# ⚠️ Ensure this matches the sample rate your server returns!
PLAYBACK_RATE = 22050 

SILENCE_LIMIT = 1.5       
SAFETY_MARGIN = 500       
SESSION_TIMEOUT = 5.0     
MIN_SPEECH_DURATION = 0.5 
CURRENT_NOISE_FLOOR = 500 

def play_sfx(filename):
    if not os.path.exists(filename): return
    try:
        wf = wave.open(filename, 'rb')
        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(), rate=wf.getframerate(), output=True)
        data = wf.readframes(1024)
        while data:
            stream.write(data)
            data = wf.readframes(1024)
        stream.stop_stream()
        stream.close()
        p.terminate()
    except: pass

class VolcoAdvertiser:
    def __init__(self):
        self.zeroconf = Zeroconf()
        self.info = None
    
    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except: IP = '127.0.0.1'
        finally: s.close()
        print(f"📡 SIGNAL ACTIVE: Broadcasting Volco on {IP}...")
        self.info = ServiceInfo(
            "_volco._tcp.local.", "Volco Device._volco._tcp.local.",
            addresses=[socket.inet_aton(IP)], port=8001,
            properties={'version': '1.0.0', 'status': 'ready'}, server="volco.local."
        )
        self.zeroconf.register_service(self.info)

    def stop(self):
        if self.info: self.zeroconf.unregister_service(self.info)
        self.zeroconf.close()

def print_audio_meter(volume, threshold, is_active, status_text="LISTENING"):
    scaled_vol = int(volume / 400) 
    if scaled_vol > 20: scaled_vol = 20
    bar = "█" * scaled_vol + "-" * (20 - scaled_vol)
    color = "\033[92m" if is_active else "\033[90m"
    reset = "\033[0m"
    sys.stdout.write(f"\r{color}🎤 {status_text} | Level: {volume:05d} | Trig: {threshold} | [{bar}]{reset}")
    sys.stdout.flush()

def calibrate_mic(duration=1.0):
    p = pyaudio.PyAudio()
    stream = p.open(format=REC_FORMAT, channels=REC_CHANNELS, rate=REC_RATE, input=True, frames_per_buffer=CHUNK)
    
    if duration > 0.6: print("\n🤫 Measuring room noise...")
    
    max_noise = 0
    start = time.time()
    while time.time() - start < duration:
        data = stream.read(CHUNK, exception_on_overflow=False)
        peak = max(struct.unpack_from("%dh" % CHUNK, data))
        if peak > max_noise: max_noise = peak
        if duration > 0.6: print_audio_meter(peak, 0, False, "CALIBRATING")
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    if max_noise < 100: max_noise = 100
    
    if duration > 0.6:
        print(f"\n✅ Noise Floor: {max_noise} | Trig: {max_noise + SAFETY_MARGIN}\n")
    
    return max_noise

# =============================
# 📡 SESSION LOGIC
# =============================
def handle_continuous_session(recorder, porcupine, ws, noise_floor):
    p = pyaudio.PyAudio()
    DYNAMIC_THRESHOLD = noise_floor + SAFETY_MARGIN
    print(f"\n🧠 Adaptive Threshold set to: {DYNAMIC_THRESHOLD}")

    connection_alive = True
    
    # Calculate how many chunks make up ~0.5 seconds of audio for our pre-roll
    MAX_PRE_BUFFER_CHUNKS = int((REC_RATE / CHUNK) * 0.5)

    try:
        while connection_alive:
            try:
                mic_stream = p.open(format=REC_FORMAT, channels=REC_CHANNELS, rate=REC_RATE, input=True, frames_per_buffer=CHUNK)
            except Exception as e:
                print(f"\n⚠️ Mic busy, giving it a second... ({e})")
                time.sleep(0.5)
                continue

            silence_start = None
            started_talking = False
            session_timer = time.time()
            speech_start_time = 0 
            valid_speech = False
            
            # This holds recent audio locally so we don't send endless silence to the server
            audio_pre_buffer = []

            while True:
                try:
                    data = mic_stream.read(CHUNK, exception_on_overflow=False)
                except Exception as e:
                    print(f"\n⚠️ Audio read error: {e}")
                    break

                if len(data) < CHUNK * 2:
                    continue
                
                try:
                    volume = max(struct.unpack_from("%dh" % CHUNK, data))
                except Exception as e:
                    continue

                is_loud = volume > DYNAMIC_THRESHOLD
                status = "RECORDING" if started_talking else "LISTENING"
                print_audio_meter(volume, DYNAMIC_THRESHOLD, is_loud or started_talking, status)

                if is_loud:
                    if not started_talking:
                        started_talking = True
                        speech_start_time = time.time()
                        
                        # 🚀 We just crossed the threshold! Send the pre-buffer so the first syllable isn't cut off.
                        try:
                            for b in audio_pre_buffer:
                                ws.send(b, opcode=websocket.ABNF.OPCODE_BINARY)
                        except Exception as e:
                            connection_alive = False
                            break
                        audio_pre_buffer.clear()
                        
                    silence_start = None 
                    session_timer = time.time()
                
                # --- ROUTING THE AUDIO ---
                if started_talking:
                    # If we are officially talking, stream directly to the server
                    try:
                        ws.send(data, opcode=websocket.ABNF.OPCODE_BINARY)
                    except Exception as e:
                        print(f"\n🔌 Connection dropped during stream: {e}")
                        connection_alive = False
                        break 
                else:
                    # If we aren't talking yet, just keep the last 0.5s of audio locally
                    audio_pre_buffer.append(data)
                    if len(audio_pre_buffer) > MAX_PRE_BUFFER_CHUNKS:
                        audio_pre_buffer.pop(0)

                # --- SILENCE TIMEOUT LOGIC ---
                if started_talking and silence_start is None and not is_loud:
                    silence_start = time.time()
                
                if started_talking and silence_start is not None:
                    total_speech_time = silence_start - speech_start_time
                    if time.time() - silence_start > SILENCE_LIMIT:
                        if total_speech_time > MIN_SPEECH_DURATION:
                            valid_speech = True
                            print(f"\n✅ Speech captured ({total_speech_time:.2f}s)")
                        else:
                            print(f"\n❌ Ignored noise ({total_speech_time:.2f}s)")
                            valid_speech = False
                            # 🧹 Tell the server to delete the short burst of noise we just sent
                            try: ws.send("CANCEL") 
                            except: pass
                        break 
                elif not started_talking:
                    if time.time() - session_timer > SESSION_TIMEOUT:
                        print("\n💤 Session Timeout.")
                        play_sfx(SFX_SLEEP)
                        mic_stream.stop_stream()
                        mic_stream.close()
                        return 

            try:
                mic_stream.stop_stream()
                mic_stream.close()
            except: pass

            if not connection_alive: return 

            if valid_speech:
                print("🚀 Sending COMMIT...")
                try: ws.send("COMMIT")
                except Exception as e: return

                print("🤖 Volco Speaking..")
                
                recorder.start()
                stop_event = threading.Event()
                
                def watch_for_interrupt():
                    while not stop_event.is_set():
                        pcm = recorder.read()
                        if porcupine.process(pcm) >= 0:
                            print("\n🛑 INTERRUPT TRIGGERED (Voice)!")
                            stop_event.set()
                        if keyboard.is_pressed(PUSH_TO_TALK_KEY):
                            print("\n🛑 INTERRUPT TRIGGERED (Button)!")
                            stop_event.set()

                t = threading.Thread(target=watch_for_interrupt)
                t.start()

                speaker_stream = p.open(format=pyaudio.paInt16, channels=1, rate=PLAYBACK_RATE, output=True)
                ws.settimeout(0.1) 
                
                while True:
                    if stop_event.is_set(): break
                    try:
                        opcode, incoming_data = ws.recv_data()
                        if stop_event.is_set(): break
                        
                        if opcode == websocket.ABNF.OPCODE_BINARY:
                            speaker_stream.write(incoming_data)
                        elif opcode == websocket.ABNF.OPCODE_TEXT:
                            msg = incoming_data.decode('utf-8')
                            if msg == "END_OF_RESPONSE" or msg == "NO_SPEECH": break
                    except websocket.WebSocketTimeoutException: continue 
                    except Exception as e:
                        connection_alive = False
                        break 
                
                ws.settimeout(None)
                stop_event.set()
                t.join()
                recorder.stop()
                
                try:
                    speaker_stream.stop_stream()
                    speaker_stream.close()
                except: pass
                
                if not connection_alive: return 
                print("\n👂 Ready for next turn...")
                play_sfx(SFX_WAKE)

    except Exception as e:
        print(f"\n🛑 Critical Session Error: {e}") 
        try: recorder.stop()
        except: pass
        return 
    finally:
        p.terminate()

# =============================
# 🚀 MAIN LOOP
# =============================
def main():
    advertiser = VolcoAdvertiser()
    advertiser.start()
    
    global CURRENT_NOISE_FLOOR
    CURRENT_NOISE_FLOOR = calibrate_mic(duration=1.0)

    porcupine = None
    recorder = None
    ws = None 
    last_ping = time.time()

    try:
        porcupine = pvporcupine.create(access_key=PICOVOICE_ACCESS_KEY, keyword_paths=[CUSTOM_WAKE_WORD_PATH]) # type: ignore
        recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
        recorder.start()

        print(f"🔌 Connecting to Brain at {WS_URL}...")
        try:
            # FIXED: Removed invalid arguments (ping_interval, ping_timeout) from create_connection
            ws = websocket.create_connection(WS_URL) 
            print("✅ Brain Connected!")
        except Exception as e:
            print(f"⚠️ Brain Offline: {e}")

        print(f"✅ VOLCO READY | Waiting for 'Hey Vella'...")
        
        while True:
            pcm = recorder.read()
            
            # 💓 IDLE HEARTBEAT
            if ws and ws.connected and (time.time() - last_ping > 20):
                try:
                    ws.send("PING")
                    last_ping = time.time()
                except:
                    ws = None

            if porcupine.process(pcm) >= 0:
                print("\n⚡ WAKE WORD DETECTED!")
                
                # 1. CHECK CONNECTION FIRST
                if ws is None or not ws.connected:
                    print("🔌 Reconnecting...")
                    try:
                        # FIXED: Removed invalid arguments here too
                        ws = websocket.create_connection(WS_URL)
                        print("✅ Reconnected.")
                    except:
                        print(f"❌ Failed.")
                        play_sfx(SFX_SLEEP)
                        continue

                # 2. SCAN ENVIRONMENT (SILENT)
                try:
                    recorder.stop()
                    print("🔍 Scanning Environment...")
                    current_noise = calibrate_mic(duration=0.5)
                    
                    # 3. NOW PLAY SOUND (MEANS "GO!")
                    play_sfx(SFX_WAKE)

                    # 4. START RECORDING
                    handle_continuous_session(recorder, porcupine, ws, current_noise)
                    
                    recorder.start()
                    print("\n✅ VOLCO READY | Waiting for 'Hey Vella'...")
                except Exception as e:
                    print(f"⚠️ Connection lost. Reconnecting...")
                    try: ws.close()
                    except: pass
                    ws = None
                    time.sleep(1)
                    recorder.start()

    except KeyboardInterrupt:
        print("\n👋 Goodbye.")
        sys.exit(0) # FIXED: Added exit to break out of the "Unkillable" loop
    finally:
        if ws: ws.close()
        advertiser.stop()
        if recorder: recorder.delete()
        if porcupine: porcupine.delete()

if __name__ == "__main__":
    while True:
        try: 
            main()
        # FIXED: Changed BaseException to Exception so it doesn't swallow sys.exit() or Ctrl+C
        except Exception as e: 
            print(f"Restarting... {e}")
            time.sleep(2)