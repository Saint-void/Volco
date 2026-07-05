# Volco — Local Voice Assistant

Volco is a compact local voice assistant that runs on Raspberry Pi hardware and macOS development machines. It combines local wake-word detection, Spotify playback control (via an optional local `librespot` client), Bluetooth data piping on Pi/Linux, and remote AI sessions. It integrates with a backend AI server (Vella) for transcription, session handling, and response generation.

**Core features:**

- Wake-word detection ("Hey Vella") and button-triggered voice sessions
- Record-and-commit audio workflow for stable ASR
- Local Spotify control using a standalone `librespot` client (optional)
- Bluetooth serial data pipe to receive user or device metadata on Pi/Linux
- GPIO sleep/wake controls on Pi, plus terminal controls on Mac/development machines

## Quick Start

### Prerequisites

- Python 3.10+ (recommended)
- Raspberry Pi OS / Debian Linux with `alsa` / `bluez` for full hardware mode, or macOS for laptop/dev mode
- `librespot` (optional, for standalone Spotify client)

Install common system dependencies (Debian/Ubuntu/Raspbian example):

```bash
sudo apt update
sudo apt install -y build-essential libasound2-dev portaudio19-dev libffi-dev libssl-dev git
```

Install common system dependencies on macOS:

```bash
brew install portaudio
```

Create a Python environment and install Python deps:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run Volco (from the `Volco/` folder):

```bash
python main.py
```

On macOS, Volco skips Pi-only Bluetooth Smart Vault, BlueALSA, RFCOMM, and GPIO setup. Press Enter in the terminal to trigger an AI session, or type `sleep` / `wake` for power-state testing. Pair Bluetooth audio through macOS System Settings if you want the Mac to act as the audio endpoint.

For laptop testing without the Bluetooth metadata pipe, provide the active profile directly:

```bash
VOLCO_USER_ID=your_user_id python main.py
```

Volco uses WebRTC data channels for device-to-server communication. It derives a signaling endpoint from `server.ws_url` in `Volco/config/settings.json` and performs an HTTP POST to `/volco_webrtc/offer`. For example, if `server.ws_url` is `ws://localhost:8001`, Volco will POST to `http://localhost:8001/volco_webrtc/offer` (use `wss://`/`https://` for secure deployments).

## Configuration

Edit runtime values in `Volco/config/settings.json`. Key settings:

- **`server.ws_url`** — base backend URL used to derive the WebRTC signaling endpoint. Example: if `server.ws_url` is `ws://<host>:8001`, Volco signals to `http://<host>:8001/volco_webrtc/offer`. Use `wss://`/`https://` for secure deployments.
- **`wakeword.model_paths`** — path or paths to wake-word model(s). Use an array when the runtime expects multiple models.
- **`wakeword.threshold`** — detection confidence threshold
- **`audio.*`** — sample rate, chunk size, sound effects, and device indexes. On macOS, `output_device_index` is ignored unless `VOLCO_OUTPUT_DEVICE_INDEX` is set.
- **`VOLCO_USER_ID`** — optional environment override for the active profile, useful on macOS where the Pi RFCOMM metadata pipe is skipped.

Wake-word model note:

- Default: `Volco/assets/models/hey_vella.onnx`
- If `settings.json` currently has a string for `model_paths` (e.g. `"./assets/models/hey_vella.onnx"`), change it to an array if your runtime expects one:


`WakeWordEngine` (in `Volco/core/wake_word.py`) reads `config["wakeword"]["model_paths"]` and will accept either a string or list in most code paths, but many wake-word libraries expect a list.

## File map (key files)

- **Main:** `Volco/main.py` — application entry point and main event loop
- **Wake-word:** `Volco/core/wake_word.py` — model loading and real-time detection loop
- **Audio I/O:** `Volco/core/audio_io.py` — mic calibration and sound effect playback
- **Connection:** `Volco/core/connection.py` — backend communication (WebRTC via `aiortc`; signaling POST to `/volco_webrtc/offer`)
- **AI session:** `Volco/modes/ai_mode/session.py` — capture/send/receive flow for voice sessions
- **Config:** `Volco/config/settings.json` — runtime configuration
- **Assets:** `Volco/assets/models/hey_vella.onnx`, `Volco/assets/sounds/*` — models and SFX
- **Tests:** `Volco/test_wakeword.py` — simple wake-word test harness

## Troubleshooting

- PyAudio / PortAudio errors: ensure `portaudio` and dev headers are installed (`portaudio19-dev` on Debian) before `pip install`.
- ALSA warnings: the code suppresses many ALSA warnings, but device conflicts can occur if other apps hold the audio device. Restart ALSA or stop other audio players.
- Wake-word not detected: verify the path in `Volco/config/settings.json` and that `Volco/assets/models/hey_vella.onnx` exists. If the wake-word library expects a list, set `model_paths` to an array.
- Bluetooth on Pi/Linux: ensure `bluez` is installed and your device is paired/connected for the `data_pipe` to operate.
- Bluetooth on macOS: pairing is handled by System Settings; the Pi-only RFCOMM metadata pipe is skipped.

## Development notes

- Use emoji-based logging markers already present in the codebase for consistent logs (e.g., ✅, ⚠️, 🧠).
- Hardware button: GPIO 17 is used by default for the smart button on Pi (click to wake, hold to sleep). Mac/development mode uses terminal controls.
- Spotify: Volco can use a local `librespot` client with an API bridge. The controller is in `core/volco_spotify.py`. Set `VOLCO_SPOTIFY_CACHE` if you want a custom cache directory.

## Testing

Run the wake-word test harness:

```bash
python test_wakeword.py
```

For integration tests, run Volco on the target hardware and exercise wake-word and Spotify interactions. Ensure the backend `server.ws_url` points at a running Vella server.

## Optional: systemd service example

Place a unit file at `/etc/systemd/system/volco.service` (adjust paths and user):

```ini
[Unit]
Description=Volco voice assistant
After=network.target

[Service]
User=pi
WorkingDirectory=/path/to/vella-modes/Volco
Environment=PATH=/path/to/venv/bin:/usr/bin
ExecStart=/path/to/venv/bin/python main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start with:

```bash
sudo systemctl enable volco
sudo systemctl start volco
```

## Contributing

Start a branch, update code and tests, and open a PR. Keep changes focused and test on a Raspberry Pi when touching hardware-specific modules.

---

If you'd like, I can also add a ready-to-install `systemd` unit or a small installer script for Raspberry Pi. Status: README synced with current code.
