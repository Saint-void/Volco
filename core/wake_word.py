import pvporcupine
from pvrecorder import PvRecorder
from config.config_manager import config

class WakeWordEngine:
    def __init__(self):
        access_key = config["picovoice"]["access_key"]
        keyword_path = config["picovoice"]["keyword_path"]
        
        print("🎧 Initializing Wake Word Engine...")
        try:
            self.porcupine = pvporcupine.create(
                access_key=access_key, 
                keyword_paths=[keyword_path]
            )
            self.recorder = PvRecorder(
                device_index=-1, 
                frame_length=self.porcupine.frame_length
            )
            print("✅ Wake Word Engine Ready!")
        except Exception as e:
            print(f"❌ Error initializing Picovoice: {e}")
            exit(1)

    def start(self):
        self.recorder.start()

    def stop(self):
        self.recorder.stop()

    def read_and_process(self):
        """Reads audio frames and returns (is_detected, raw_pcm_data)."""
        pcm = self.recorder.read()
        result = self.porcupine.process(pcm)
        return result >= 0, pcm

    def cleanup(self):
        if self.recorder:
            self.recorder.delete()
        if self.porcupine:
            self.porcupine.delete()