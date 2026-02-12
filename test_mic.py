import sounddevice as sd
import numpy as np

def calibrate():
    print("Stay silent... measuring noise floor...")
    with sd.InputStream(samplerate=16000, channels=1, dtype='int16') as stream:
        for _ in range(300): # Test for 3 seconds
            chunk, _ = stream.read(1600)
            volume = np.sqrt(np.mean(chunk.astype(float)**2))
            print(f"Current Volume: {volume:.2f}")

calibrate()