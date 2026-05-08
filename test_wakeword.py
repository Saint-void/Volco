import numpy as np
import pyaudio
from openwakeword.model import Model
import time

# --- CONFIG ---
MODEL_PATHS = [
    "./assets/models/hey_vella.onnx",
    "./assets/models/vella2.onnx",
    "./assets/models/vella1.onnx",
    "./assets/models/vellla.onnx",
    "./assets/models/vellla (1).onnx",
    "./assets/models/vellla (2).onnx",
    "alexa"
]
THRESHOLD = 0.4
CHUNK_SIZE = 1280
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def test_engine():
    print(f"🔍 Loading models: {MODEL_PATHS}")
    try:
        owwModel = Model(
            wakeword_models=MODEL_PATHS,
            inference_framework="onnx"
        )
        print(f"✅ Models loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load models: {e}")
        return

    pa = pyaudio.PyAudio()
    last_trigger = 0
    cooldown = 1.0 # 1 second cooldown
    
    try:
        stream = pa.open(
            rate=RATE,
            channels=CHANNELS,
            format=FORMAT,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        print(f"🎤 Microphone open (Anti-duplicate enabled)")
    except Exception as e:
        print(f"❌ Failed to open microphone: {e}")
        return

    print("\n--- STARTING STABLE TEST ---")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)

            prediction = owwModel.predict(audio_data)

            if prediction:
                output = []
                triggered = False
                for name, score in prediction.items():
                    short_name = name.split("/")[-1].split("\\")[-1]
                    output.append(f"{short_name}: {score:.4f}")
                    if score >= THRESHOLD:
                        triggered = True
                
                max_score = max(prediction.values())
                if max_score > 0.05:
                    status = "..."
                    if triggered:
                        if (time.time() - last_trigger) > cooldown:
                            status = "🔥 TRIGGERED!"
                            last_trigger = time.time()
                        else:
                            status = "⏳ DEBOUNCED"
                    
                    print(f"[{status}] {', '.join(output)}")

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()

if __name__ == "__main__":
    test_engine()
