import numpy as np
import pyaudio
from openwakeword.model import Model
import time

# --- CONFIG ---
# We will use the built-in "alexa" or "hey_jarvis" model for stability
CHOSEN_MODEL = "alexa" 
THRESHOLD = 0.5
CHUNK_SIZE = 1280
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def test_engine():
    print(f"🔍 Loading built-in model: {CHOSEN_MODEL}")
    try:
        # Load with built-in model name instead of a path
        owwModel = Model(
            wakeword_models=[CHOSEN_MODEL],
            inference_framework="onnx"
        )
        print(f"✅ Model '{CHOSEN_MODEL}' loaded successfully!")
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

    print("\n--- STARTING STABILITY TEST ---")
    print(f"Say '{CHOSEN_MODEL.upper()}' (Threshold: {THRESHOLD})")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            # REAL-TIME CATCH UP
            available = stream.get_read_available()
            if available > CHUNK_SIZE * 2:
                skip_chunks = (available // CHUNK_SIZE) - 1
                stream.read(skip_chunks * CHUNK_SIZE, exception_on_overflow=False)

            # Read audio data
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)

            # Predict
            prediction = owwModel.predict(audio_data)

            if prediction:
                output = []
                triggered = False
                for name, score in prediction.items():
                    # Display the score
                    output.append(f"{name}: {score:.4f}")
                    if score >= THRESHOLD:
                        triggered = True
                
                max_score = max(prediction.values())
                if max_score > 0.05: # Sensitivity floor for printing
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
