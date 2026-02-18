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

PICOVOICE_ACCESS_KEY = "Sl361++BBZqn4rQXFqhoMICzrkMMg13QUDhlBU73myt6WcR93sbZMg==" 
PUSH_TO_TALK_KEY = "right shift"
CUSTOM_WAKE_WORD_PATH = "./assets/Hey-Vella_en_windows_v4_0_0.ppn" 

SFX_WAKE = "./assets/sounds/wake.wav"
SFX_SLEEP = "./assets/sounds/sleep.wav"

REC_FORMAT = pyaudio.paInt16
REC_CHANNELS = 1
REC_RATE = 16000
CHUNK = 512

SILENCE_LIMIT = 0.5       
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
# 📡 SESSION LOGIC (NO HEARTBEAT HERE)
# =============================
def handle_continuous_session(recorder, porcupine, ws):
    p = pyaudio.PyAudio()
    DYNAMIC_THRESHOLD = CURRENT_NOISE_FLOOR + SAFETY_MARGIN
    connection_alive = True

    try:
        while connection_alive:
            # --- PHASE 1: LISTEN ---
            mic_stream = p.open(format=REC_FORMAT, channels=REC_CHANNELS, rate=REC_RATE, input=True, frames_per_buffer=CHUNK)
            silence_start = None
            started_talking = False
            session_timer = time.time()
            speech_start_time = 0 
            valid_speech = False

            while True:
                data = mic_stream.read(CHUNK, exception_on_overflow=False)
                
                # ⚡ Just send data. No PINGs here. Audio keeps it alive.
                try:
                    ws.send_binary(data)
                except:
                    connection_alive = False
                    break 
                
                volume = max(struct.unpack_from("%dh" % CHUNK, data))
                is_loud = volume > DYNAMIC_THRESHOLD
                status = "RECORDING" if started_talking else "LISTENING"
                print_audio_meter(volume, DYNAMIC_THRESHOLD, is_loud or started_talking, status)

                if is_loud:
                    if not started_talking:
                        started_talking = True
                        speech_start_time = time.time()
                    silence_start = None 
                    session_timer = time.time()
                elif started_talking:
                    if silence_start is None: silence_start = time.time()
                    total_speech_time = silence_start - speech_start_time
                    if time.time() - silence_start > SILENCE_LIMIT:
                        if total_speech_time > MIN_SPEECH_DURATION:
                            valid_speech = True
                            print(f"\n✅ Speech captured ({total_speech_time:.2f}s)")
                        else:
                            print(f"\n❌ Ignored noise ({total_speech_time:.2f}s)")
                            valid_speech = False
                        break 
                else:
                    if time.time() - session_timer > SESSION_TIMEOUT:
                        print("\n💤 Session Timeout.")
                        play_sfx(SFX_SLEEP)
                        mic_stream.stop_stream()
                        mic_stream.close()
                        p.terminate()
                        return # Exit to main loop (Heartbeat will resume there)

            mic_stream.stop_stream()
            mic_stream.close()

            if not connection_alive: raise Exception("Socket died")

            if valid_speech:
                print("🚀 Sending COMMIT...")
                ws.send("COMMIT")
                print("🤖 Volco Speaking... (Say 'Hey Vella' to Interrupt)")
                
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

                speaker_stream = p.open(format=pyaudio.paInt16, channels=1, rate=22050, output=True)
                
                while True:
                    if stop_event.is_set(): break
                    try:
                        opcode, data = ws.recv_data()
                        if stop_event.is_set(): break
                        if opcode == websocket.ABNF.OPCODE_BINARY:
                            speaker_stream.write(data)
                        elif opcode == websocket.ABNF.OPCODE_TEXT:
                            msg = data.decode('utf-8')
                            if msg == "END_OF_RESPONSE": break
                            elif msg == "NO_SPEECH": break
                    except Exception as e:
                        print(f"Socket Error: {e}")
                        connection_alive = False
                        break 
                
                stop_event.set()
                t.join()
                recorder.stop()
                speaker_stream.stop_stream()
                speaker_stream.close()
                
                if not connection_alive: raise Exception("Socket died")
                print("\n👂 Ready for next turn...")
            else:
                pass
            
    except Exception as e:
        # Don't print huge error, just say reset
        # print(f"\n❌ Session Error: {e}") 
        try: recorder.stop()
        except: pass
        raise e
    finally:
        p.terminate()

# =============================
# 🚀 MAIN LOOP (HEARTBEAT LIVES HERE)
# =============================
def main():
    advertiser = VolcoAdvertiser()
    advertiser.start()
    calibrate_mic()

    porcupine = None
    recorder = None
    ws = None 
    last_ping = time.time()

    try:
        porcupine = pvporcupine.create(access_key=PICOVOICE_ACCESS_KEY, keyword_paths=[CUSTOM_WAKE_WORD_PATH])
        recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
        recorder.start()

        print(f"🔌 Connecting to Brain at {WS_URL}...")
        try:
            ws = websocket.create_connection(WS_URL)
            print("✅ Brain Connected!")
        except Exception as e:
            print(f"⚠️ Brain Offline: {e}")

        print(f"✅ VOLCO READY | Waiting for 'Hey Vella'...")
        
        while True:
            pcm = recorder.read()
            
            # 💓 IDLE HEARTBEAT (Only when waiting)
            # This keeps the connection open during long silences
            if ws and ws.connected and (time.time() - last_ping > 20):
                try:
                    ws.send("PING")
                    last_ping = time.time()
                except:
                    ws = None # Mark dead

            if porcupine.process(pcm) >= 0:
                print("\n⚡ WAKE WORD DETECTED!")
                play_sfx(SFX_WAKE) 
                
                # RECONNECT IF NEEDED
                if ws is None or not ws.connected:
                    print("🔌 Reconnecting...")
                    try:
                        ws = websocket.create_connection(WS_URL)
                        print("✅ Reconnected.")
                    except:
                        print(f"❌ Failed.")
                        play_sfx(SFX_SLEEP)
                        continue

                try:
                    recorder.stop()
                    handle_continuous_session(recorder, porcupine, ws)
                    recorder.start()
                    print("\n✅ VOLCO READY | Waiting for 'Hey Vella'...")
                except Exception as e:
                    print(f"⚠️ Connection refreshed.")
                    ws = None
                    recorder.start()

    except KeyboardInterrupt:
        print("\n👋 Goodbye.")
    finally:
        if ws: ws.close()
        advertiser.stop()
        if recorder: recorder.delete()
        if porcupine: porcupine.delete()

if __name__ == "__main__":
    while True:
        try: main()
        except BaseException as e:
            print(f"Restarting... {e}")
            time.sleep(2)