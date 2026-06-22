# Volco — Local Voice Assistant

Volco is a compact, Raspberry-Pi-oriented voice assistant that combines local wake-word detection, Spotify playback control (via a local librespot client), Bluetooth data piping, and remote AI sessions. It is designed to run on edge hardware and integrate with a backend AI server for transcription and response generation.

**Core features:**

- Wake-word detection ("Hey Vella") and button-triggered voice sessions
- Record-and-commit audio workflow for stable ASR
- Local Spotify control using a standalone `librespot` client
- Bluetooth serial data pipe to receive user or device metadata
- Simple hardware controls for sleep/wake and volume ducking

## Quick Start

Prerequisites:

- Python 3.10+ (recommended)
- A Debian-based Linux system (Raspberry Pi OS recommended) with `alsa` / `bluez` installed
- `librespot` (optional, for standalone Spotify client)

Install system dependencies (Debian/Ubuntu/Raspbian example):

```bash
sudo apt update
sudo apt install -y build-essential libasound2-dev portaudio19-dev libffi-dev libssl-dev git
```

Create a Python environment and install Python deps:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run Volco:

```bash
python main.py
```

## Configuration

Edit configuration values in [Volco/config/settings.json](Volco/config/settings.json). Key settings:

- **`server.ws_url`** — backend AI WebSocket/WebRTC endpoint
- **`wakeword.model_paths`** — path or paths to wake-word model(s)
- **`wakeword.threshold`** — detection confidence threshold
- **`audio.*`** — sample rate, chunk size, sound effects, and device indexes

Wake-word model note:

- The default wake-word model is located at [Volco/assets/models/hey_vella.onnx](Volco/assets/models/hey_vella.onnx).
- In the current `settings.json` the `model_paths` value is a string (`"./assets/models/hey_vella.onnx"`). If detection fails or your wake-word backend expects a list, change it to an array, e.g.:

```json
"wakeword": {
  "model_paths": ["./assets/models/hey_vella.onnx"],
  "threshold": 0.3
}
```

`WakeWordEngine` (in [Volco/core/wake_word.py](Volco/core/wake_word.py)) reads `config["wakeword"]["model_paths"]` and passes it to the wake-word runtime.

## File map (key files)

- **Main:** [Volco/main.py](Volco/main.py) — application entry point and main event loop
- **Wake-word:** [Volco/core/wake_word.py](Volco/core/wake_word.py) — model loading and real-time detection loop
- **Audio I/O:** [Volco/core/audio_io.py](Volco/core/audio_io.py) — mic calibration and sound effect playback
- **Connection:** [Volco/core/connection.py](Volco/core/connection.py) — backend communication (WebSocket/WebRTC)
- **AI session:** [Volco/modes/ai_mode/session.py](Volco/modes/ai_mode/session.py) — capture/send/receive flow for voice sessions
- **Config:** [Volco/config/settings.json](Volco/config/settings.json) — runtime configuration
- **Assets:** [Volco/assets/models/hey_vella.onnx](Volco/assets/models/hey_vella.onnx), [Volco/assets/sounds/\*](Volco/assets/sounds/) — models and SFX
- **Tests:** [Volco/test_wakeword.py](Volco/test_wakeword.py) — simple wake-word test harness

## Troubleshooting

- PyAudio install errors: ensure `portaudio` and dev headers are installed (`portaudio19-dev` on Debian) before `pip install`.
- ALSA warnings: the code suppresses many ALSA warnings, but device conflicts can occur if other apps hold the audio device. Restart ALSA or stop other audio players.
- Wake-word not detected: verify the path in [Volco/config/settings.json](Volco/config/settings.json) and that [Volco/assets/models/hey_vella.onnx](Volco/assets/models/hey_vella.onnx) exists. If the wake-word library expects a list, set `model_paths` to an array.
- Bluetooth: ensure `bluez` is installed and your device is paired/connected for the `data_pipe` to operate.

## Development notes

- Use emoji-based logging markers already present in the codebase for consistent logs (e.g., ✅, ⚠️, 🧠).
- Hardware button: GPIO 17 is used by default for the smart button (click to wake, hold to sleep).
- Spotify: Volco uses a local `librespot` client and an API bridge. Start/stop is handled by `core/volco_spotify.py`.

## Testing

Run the wake-word test harness:

```bash
python test_wakeword.py
```

For broader integration tests, run Volco on the target hardware and exercise wake-word and Spotify interactions.

## Contributing

Start a branch, update code and tests, and open a PR. Keep changes focused and test on a Raspberry Pi when touching hardware-specific modules.

---

If you want, I can also:

- Add a systemd service file to run Volco on boot
- Create a short setup script to install system packages on Raspberry Pi

Status: README updated.
