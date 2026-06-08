# Volco AI Assistant - Version 7.2.1 Reversion

## Change Log (June 8, 2026)

### 🔄 Reversion to Record-and-Commit Model
Reverted the voice processing system from a streaming architecture back to the "Record-and-Commit" model to improve stability and alignment with current hardware performance constraints.

**Key Changes:**
- **Server-Side (`Vella-Server/volco/router.py`):**
    - Removed real-time streaming ASR updates.
    - Implemented a `bytearray` buffer in the WebRTC Data Channel to collect audio chunks.
    - Transcription now only occurs upon receiving the `COMMIT` signal, processing the entire accumulated buffer as a single segment.
    - Maintained WebRTC PeerConnection and DataChannel architecture.
- **Client-Side (`Volco/core/connection.py`):**
    - Restored WebRTC connection management logic.
    - Ensured compatibility with the record-and-commit workflow in `modes/ai_mode/session.py`.
- **Dependencies:**
    - Removed `websocket-client` from `Volco/requirements.txt` as WebRTC remains the primary communication protocol.

### 🧠 Database Refactor
Refactored `Vella-Server/db.py` to use **SQLAlchemy** for better session management and integration with FastAPI's dependency injection system.
- Added `SQLAlchemy` to `Vella-Server/requirements.txt`.
- Migrated raw SQL table definitions to declarative SQLAlchemy models (`User`, `Session`, `Message`).
- Updated `main.py` endpoints to use the `get_db` dependency.

---
**Status:** ✅ Reversion Complete | 🟢 WebRTC Active | 🗄️ SQL Refactor Applied
