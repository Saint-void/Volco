
---

# Volco

Volco is your personal AI assistant + music companion built to run on a Raspberry Pi. It listens for wake words, handles AI sessions, integrates with Spotify, and supports Bluetooth data piping from your phone.

This README covers installation, setup, dependencies, and operation details.

---

## 🖥 System Requirements

* Raspberry Pi 4 (recommended) or Pi 3+
* Raspbian / Raspberry Pi OS (64-bit preferred)
* Python 3.10+
* At least 8 GB SD card (for caching audio & Spotify)
* USB mic or onboard mic support
* Bluetooth-enabled Pi if using the data pipe

---

## 📦 Project Structure

```text
VOLCO/
├── assets/
│   ├── models/       # ML / AI models
│   └── sounds/       # Notification & session sounds
├── config/
│   ├── config_manager.py   # Config loader
│   ├── config_notes.txt
│   └── settings.json       # Main config file
├── core/
│   ├── audio_io.py
│   ├── ble_server.py
│   ├── connection.py
│   ├── current_user.txt    # Stores the active user ID
│   ├── data_pipe.py        # Bluetooth serial pipe
│   ├── volco_audio_engine.py
│   ├── volco_spotify.py
│   └── wake_word.py
├── modes/
│   ├── ai_mode/
│   │   └── session.py
│   └── bt_mode/
│       └── __init__.py
├── app_listener.py
├── main.py                 # Entry point
├── requirements.txt
├── readme.md
└── .gitignore
```

---

## ⚙ Installation

1. **Update system packages**

```bash
sudo apt update && sudo apt upgrade -y
```

2. **Install Python & dev tools**

```bash
sudo apt install -y python3 python3-pip python3-venv build-essential libasound2-dev portaudio19-dev
```

3. **Create a virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate
```

4. **Install Python dependencies**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

5. **Bluetooth setup (optional for data pipe)**

```bash
sudo apt install -y bluetooth bluez python3-serial
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
```

6. **Optional: Install `librespot` for Spotify playback**

```bash
sudo apt install -y librespot
```

* Ensure your cached Spotify tokens are in `~/.cache/volco_spotify`.

---

## 🔑 Configuration

1. Copy `config/settings.json.example` → `config/settings.json` and edit values:

   * Audio chunk size, rate, channels
   * Thresholds for wake word and noise
   * Output device index for playback
2. Add your Spotify `CLIENT_ID` and `CLIENT_SECRET` in `core/volco_spotify.py`.
3. Update Picovoice wake word credentials in `config/settings.json`.

---

## 🎵 Spotify Integration

* Uses official Spotify API to search/play tracks, albums, and playlists.
* Controls: `next`, `previous`, `pause`, `resume`.
* Standalone playback via `librespot` or OS audio output.
* Discovery of Volco device is automatic on startup.

---

## 🎤 Wake Word & AI Session

* Uses **Picovoice Porcupine** for hotword detection.

* When wake word detected:

  * Starts AI listening session
  * Captures speech above adaptive threshold
  * Sends audio to AI engine (`ai_mode/session.py`)
  * Volco can respond with audio or trigger Spotify commands

* Push-to-talk button is fallback for Pi setups without working Porcupine engine.

---

## 📡 Bluetooth Data Pipe

* Runs in the background using `/dev/rfcomm0`.
* Connects your phone via Bluetooth and receives user data:

  * Example: `DB_ID:<user_id>` → automatically stores in `current_user.txt`
* Handles serial errors gracefully and waits for the next connection.

---

## 🚀 Running Volco

1. Activate virtual environment

```bash
source venv/bin/activate
```

2. Run main app

```bash
python main.py
```

* The system auto-initializes:

  * Wake word engine
  * Spotify manager
  * Data pipe listener
* LED / terminal logs show status for audio, AI sessions, and Spotify commands.

---

## 🧩 Developer Notes

* AI sessions are handled in `modes/ai_mode/session.py`
* Spotify playback engine is `core/volco_spotify.py`
* Wake word engine is `core/wake_word.py`
* Bluetooth serial pipe is `core/data_pipe.py`
* Audio I/O & meters are in `core/audio_io.py`

---

## ⚠️ Troubleshooting

* **Mic not detected:** check `arecord -l` and adjust channels in `settings.json`.
* **Spotify playback fails:** ensure `librespot` is installed and Spotify token is valid.
* **Wake word fails:** Picovoice requires valid access key and keyword path.
* **Bluetooth issues:** make sure `rfcomm` is free, or run `sudo rfcomm release /dev/rfcomm0`.

---

## 📝 Logging & Debugging

* Console prints show AI session status, Spotify commands, and Bluetooth messages.
* Look for `✅` and `⚠️` markers for success/warning messages.

---

## 🛠 Contributing

* All changes should be tested on a Pi before merge
* Maintain consistent logging and emoji-based markers for readability
* Keep Spotify keys and tokens secure, never commit them to git

---

