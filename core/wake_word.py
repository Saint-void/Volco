import time
import struct
import pyaudio
import pvporcupine
from config.config_manager import config

class WakeWordEngine:
    def __init__(self):
        self.porcupine = None
        self.pa = pyaudio.PyAudio()
        self.audio_stream = None
        self.is_functional = False

        try:
            print("🎧 Initializing Wake Word Engine...")
            self.porcupine = pvporcupine.create(
                access_key=config["picovoice"]["access_key"],
                keyword_paths=[config["picovoice"]["keyword_path"]]
            )
            self.is_functional = True
            print("✅ Wake Word Engine Ready!")
            
        except Exception as e:
            print(f"\n⚠️ [WARNING] Wake Word Engine Failed to Load.")
            print(f"   -> Details: {e}")
            print("⚙️ [SYSTEM] Volco degrading to BUTTON-ONLY mode (Push-to-Talk).")
            self.is_functional = False

    def start(self):
        """Opens the microphone stream for the wake word."""
        # ⚡ FIX: Explicitly check if porcupine is None to satisfy the linter
        if not self.is_functional or self.porcupine is None: 
            return 
            
        try:
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length
            )
        except Exception as e:
            print(f"⚠️ Wake Word Mic Error: {e}")
            self.is_functional = False

    def read_and_process(self):
        """Reads audio and checks for the wake word."""
        # ⚡ FIX: Explicit None checks here as well
        if not self.is_functional or self.porcupine is None or self.audio_stream is None:
            time.sleep(0.1) 
            return False, -1

        try:
            pcm = self.audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
            result = self.porcupine.process(pcm)
            return result >= 0, result
        except Exception:
            return False, -1

    def stop(self):
        """Closes the wake word microphone stream."""
        if self.audio_stream is not None:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except: 
                pass
            self.audio_stream = None