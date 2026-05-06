import numpy as np
import pyaudio
from openwakeword.model import Model
import time

# --- CONFIG ---
MODEL_PATH = "./assets/models/hey_vella.onnx"
THRESHOLD = 0.5
CHUNK_SIZE = 1280
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def test_engine():
    print(f"🔍 Loading model: {MODEL_PATH}")
    try:
        # Initialize openWakeWord
        owwModel = Model(
            wakeword_models=[MODEL_PATH],
            inference_framework="onnx"
        )
        print("✅ Model loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return

    # Initialize PyAudio
    pa = pyaudio.PyAudio()
    
    try:
        stream = pa.open(
            rate=RATE,
            channels=CHANNELS,
            format=FORMAT,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        print(f"🎤 Microphone open (Rate: {RATE}, Chunk: {CHUNK_SIZE})")
    except Exception as e:
        print(f"❌ Failed to open microphone: {e}")
        return

    print("\n--- STARTING TEST ---")
    print(f"Say 'Hey Vella' (Threshold: {THRESHOLD})")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            # Read audio data
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)

            # Predict
            # Returns a dict like {'hey_vella': 0.12}
            prediction = owwModel.predict(audio_data)

            if prediction:
                # Print all scores to see what keys the model is using
                output = []
                triggered = False
                for name, score in prediction.items():
                    # Clean up the name for display (remove path)
                    short_name = name.split("/")[-1].split("\\")[-1]
                    output.append(f"{short_name}: {score:.4f}")
                    if score >= THRESHOLD:
                        triggered = True
                
                # Only print if there's some activity to avoid flooding
                max_score = max(prediction.values())
                if max_score > 0.01:
                    status = "🔥 TRIGGERED!" if triggered else "..."
                    print(f"[{status}] {', '.join(output)}")

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()

if __name__ == "__main__":
    test_engine()
