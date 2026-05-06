import time
import numpy as np
import pyaudio
from openwakeword.model import Model
from config.config_manager import config

class WakeWordEngine:
    def __init__(self):
        self.model = None
        self.pa = pyaudio.PyAudio()
        self.audio_stream = None
        self.is_functional = False
        self.chunk_size = 1280  # openWakeWord default (80ms)
        self.sample_rate = 16000
        
        try:
            print("🎧 Initializing openWakeWord Engine...")
            
            # Ensure base models are present
            import openwakeword
            openwakeword.utils.download_models()
            
            model_path = config["openwakeword"]["model_path"]
            self.model = Model(
                wakeword_models=[model_path],
                inference_framework="onnx"
            )
            self.is_functional = True
            print(f"✅ Wake Word Engine Ready (Model: {model_path})")
            
        except Exception as e:
            print(f"\n⚠️ [WARNING] Wake Word Engine Failed to Load.")
            print(f"   -> Details: {e}")
            print("⚙️ [SYSTEM] Volco degrading to BUTTON-ONLY mode (Push-to-Talk).")
            self.is_functional = False

    def start(self):
        """Opens the microphone stream for the wake word."""
        if not self.is_functional or self.model is None: 
            return 
            
        try:
            # We use a smaller 'frames_per_buffer' in the stream to reduce latency,
            # but we will still read 'self.chunk_size' at a time.
            self.audio_stream = self.pa.open(
                rate=self.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            # Flush the initial buffer to ensure we start with fresh audio
            if self.audio_stream.get_read_available() > 0:
                self.audio_stream.read(self.audio_stream.get_read_available(), exception_on_overflow=False)
                
        except Exception as e:
            print(f"⚠️ Wake Word Mic Error: {e}")
            self.is_functional = False

    def read_and_process(self):
        """Reads audio and checks for the wake word."""
        if not self.is_functional or self.model is None or self.audio_stream is None:
            time.sleep(0.1) 
            return False, 0

        try:
            # Check how much audio is waiting. If there's too much, we are lagging.
            # We want to catch up to the "now".
            available = self.audio_stream.get_read_available()
            if available > self.chunk_size * 2:
                # Skip the old data to get to the most recent audio
                skip_chunks = (available // self.chunk_size) - 1
                self.audio_stream.read(skip_chunks * self.chunk_size, exception_on_overflow=False)

            pcm = self.audio_stream.read(self.chunk_size, exception_on_overflow=False)
            audio_data = np.frombuffer(pcm, dtype=np.int16)
            
            prediction = self.model.predict(audio_data)
            
            if prediction:
                confidence = max(prediction.values())
                threshold = config.get("openwakeword", {}).get("threshold", 0.3)
                return confidence >= threshold, confidence
            
            return False, 0
        except Exception:
            return False, 0

    def stop(self):
        """Closes the wake word microphone stream."""
        if self.audio_stream is not None:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except: 
                pass
            self.audio_stream = None

    def cleanup(self):
        """Safely shuts down the engine and frees memory."""
        self.stop()
        self.model = None
        if self.pa is not None:
            self.pa.terminate()
