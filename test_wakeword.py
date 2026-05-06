import numpy as np
import pyaudio
from openwakeword.model import Model
import time

# --- CONFIG ---
MODEL_PATH = "./assets/models/hey_vella.onnx"
THRESHOLD = 0.3 # Matching your new settings
CHUNK_SIZE = 1280
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def test_engine():
    print(f"🔍 Loading model: {MODEL_PATH}")
    try:
        owwModel = Model(
            wakeword_models=[MODEL_PATH],
            inference_framework="onnx"
        )
        print("✅ Model loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return

    pa = pyaudio.PyAudio()
    
    try:
        stream = pa.open(
            rate=RATE,
            channels=CHANNELS,
            format=FORMAT,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        # Flush initial noise
        if stream.get_read_available() > 0:
            stream.read(stream.get_read_available(), exception_on_overflow=False)
            
        print(f"🎤 Microphone open (Real-time catch-up enabled)")
    except Exception as e:
        print(f"❌ Failed to open microphone: {e}")
        return

    print("\n--- STARTING TEST ---")
    print(f"Say 'Hey Vella' (Threshold: {THRESHOLD})")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            # ⚡ REAL-TIME CATCH UP
            # If the buffer has more than 2 chunks, skip the old ones to stay at "now"
            available = stream.get_read_available()
            if available > CHUNK_SIZE * 2:
                skip_chunks = (available // CHUNK_SIZE) - 1
                stream.read(skip_chunks * CHUNK_SIZE, exception_on_overflow=False)

            # Read the latest chunk
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
                if max_score > 0.1: # Only print if there is significant sound
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
