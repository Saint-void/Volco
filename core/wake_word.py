import time
import numpy as np
import pyaudio
from openwakeword.model import Model
from config.config_manager import config
from core.audio_io import suppress_alsa_stderr


class WakeWordEngine:
    def __init__(self):
        self.model = None
        with suppress_alsa_stderr():
            self.pa = pyaudio.PyAudio()
        self.audio_stream = None
        self.is_functional = False
        self.chunk_size = 1280  
        self.sample_rate = 16000
        
        # Pull threshold once at init
        self.threshold = config.get("openwakeword", {}).get("threshold", 0.4)
        
        # Anti-Duplicate / Debounce state
        self.last_activation_time = 0
        self.activation_cooldown = 1.0  # seconds
        self.rearm_threshold = self.threshold * 0.5
        self.rearm_quiet_frames = 3
        self._quiet_frames = self.rearm_quiet_frames
        self._armed = True
        self._suppress_until = 0

        try:
            print("🎧 Initializing openWakeWord Engine (Optimized Ensemble)...")
            
            # Ensure base models are present
            import openwakeword
            openwakeword.utils.download_models()
            
            model_paths = config["openwakeword"].get("model_paths", ["alexa"])
            
            self.model = Model(
                wakeword_models=model_paths,
                inference_framework="onnx",
                vad_threshold=0.5  # ⚡ Only process if 50% sure it's human speech
            )
            
            self.is_functional = True
            print(f"✅ Wake Word Engine Ready (Models: {model_paths} | Threshold: {self.threshold})")
            
        except Exception as e:
            print(f"\n⚠️ [WARNING] Wake Word Engine Failed to Load.")
            print(f"   -> Details: {e}")
            self.is_functional = False

    def start(self):
        """Opens the microphone stream for the wake word."""
        if not self.is_functional or self.model is None: 
            return 
            
        try:
            with suppress_alsa_stderr():
                self.audio_stream = self.pa.open(
                    rate=self.sample_rate,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=self.chunk_size
                )
            self.reset_detection_state(suppress_seconds=0.8, require_rearm=True)
        except Exception as e:
            print(f"⚠️ Wake Word Mic Error: {e}")
            self.is_functional = False

    def reset_detection_state(self, suppress_seconds=0.0, require_rearm=True):
        """Clears wake-word memory so an old activation cannot fire again."""
        self.last_activation_time = 0
        self._quiet_frames = 0 if require_rearm else self.rearm_quiet_frames
        self._armed = not require_rearm
        self._suppress_until = time.monotonic() + suppress_seconds

        reset = getattr(self.model, "reset", None)
        if callable(reset):
            try:
                reset()
            except Exception:
                pass

    def read_and_process(self):
        """Reads audio and checks for the wake word."""
        if not self.is_functional or self.model is None or self.audio_stream is None:
            time.sleep(0.1) 
            return False, 0

        try:
            pcm = self.audio_stream.read(self.chunk_size, exception_on_overflow=False)
            audio_data = np.frombuffer(pcm, dtype=np.int16)
            
            prediction = self.model.predict(audio_data)
            
            if prediction:
                confidence = max(prediction.values())

                if confidence <= self.rearm_threshold:
                    self._quiet_frames += 1
                    if self._quiet_frames >= self.rearm_quiet_frames:
                        self._armed = True
                else:
                    self._quiet_frames = 0

                if time.monotonic() < self._suppress_until:
                    return False, confidence
                
                # Check threshold
                if self._armed and confidence >= self.threshold:
                    current_time = time.time()
                    # ⚡ Check cooldown to prevent duplicate triggers
                    if (current_time - self.last_activation_time) > self.activation_cooldown:
                        self.last_activation_time = current_time
                        self._armed = False
                        self._quiet_frames = 0
                        return True, confidence
            
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
