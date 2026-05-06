 # Volco Project Context

Volco is a personal AI assistant and music companion designed for Raspberry Pi, integrating voice interaction, Spotify playback, and Bluetooth connectivity.

## Project Overview

*   **Main Technologies:** Python 3.10+, openWakeWord (Wake Word), PyAudio (Audio I/O), librespot (Spotify hardware client), WebSockets (Backend communication), Bleak/BlueZ (Bluetooth).
*   **Core Functionality:**
    *   **Wake Word Detection:** Uses `openWakeWord` to listen for "Hey Vella".
    *   **AI Sessions:** Captures voice after wake word/button trigger, sends to a remote AI engine via WebSockets, and plays back responses.
    *   **Spotify Integration:** Full playback control (play, pause, next, prev, search) via a custom API engine and a local `librespot` daemon.
    *   **Bluetooth Data Pipe:** Receives user data (e.g., user IDs) via a serial Bluetooth connection (`/dev/rfcomm0`).
    *   **Hardware Control:** Supports physical buttons for triggering AI sessions and toggling power states (deep sleep/wake).

## Architecture

*   `main.py`: Entry point. Manages initialization, the main event loop, power states, and hardware interrupts.
*   `core/`: Core system modules.
    *   `audio_io.py`: Microphone calibration and sound effect playback.
    *   `volco_audio_engine.py` & `volco_spotify.py`: Spotify API and hardware management.
    *   `wake_word.py`: Wrapper for openWakeWord.
    *   `connection.py`: WebSocket manager for backend AI communication.
    *   `data_pipe.py`: Bluetooth serial communication listener.
*   `modes/`: High-level operational modes.
    *   `ai_mode/session.py`: Logic for active listening, "thinking" sounds, and processing AI responses/commands.
*   `config/`: Configuration management via `settings.json` and `config_manager.py`.
*   `assets/`: Storage for ML models (`.onnx`) and WAV sound effects.

## Building and Running

*   **Setup Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
*   **Run Application:**
    ```bash
    python main.py
    ```
*   **External Dependencies:** Requires `librespot` for Spotify and `bluez` for Bluetooth functionality.
*   **Configuration:** Copy and edit `config/settings.json`. Ensure openWakeWord model path and Spotify credentials are set.

## Development Conventions

*   **Logging:** Use consistent emoji-based markers for status (e.g., ✅ for success, ⚠️ for warnings, ⚡ for triggers, 🧠 for AI processing).
*   **Audio Safety:** Always handle ALSA device locking carefully, especially when switching between Spotify and AI voice output.
*   **Concurrency:** Use `threading` for background tasks (e.g., sound loops, data pipe, Spotify pre-caching).
*   **Hardware:** GPIO 17 is the default pin for the smart button (Click to wake, 3s Hold for sleep).
*   **Testing:** All changes should be verified on a Raspberry Pi environment to ensure compatibility with hardware-specific libraries like `gpiozero` and `openwakeword`.

## Key Files for Reference

*   `main.py`: Main loop and system orchestration.
*   `modes/ai_mode/session.py`: Voice interaction logic.
*   `core/volco_spotify.py`: Spotify playback integration.
*   `config/settings.json`: System-wide parameters (audio rates, thresholds, API URLs).
