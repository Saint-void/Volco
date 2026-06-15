import json
import time
import pyaudio
import threading
import platform
import sys
import select
import audioop
from core.volco_audio_engine import VolcoSpotifyEngine
from config.config_manager import config
from core.audio_io import play_sfx, print_audio_meter, suppress_alsa_stderr
from core.audio_pipeline import AudioPipelineConfig, EndpointingAudioPipeline
from core.assistant_processor import get_assistant_processor
from core.state_machine import VoiceSessionStateMachine

# Initialize the engine once
spotify = VolcoSpotifyEngine()
assistant_processor = get_assistant_processor()

import select

def is_button_pressed():
    """Checks for Space/Shift on Windows, or the 'Enter' key on Linux."""
        # Non-blocking check to see if 'Enter' was pressed in the Linux terminal
    i, _, _ = select.select([sys.stdin], [], [], 0.0)
    if i:
        sys.stdin.readline() # Clear the buffer
        return True
    return False


def _send_audio_segment(conn_manager, pcm: bytes, chunk_size: int = 24000) -> bool:
    for offset in range(0, len(pcm), chunk_size):
        if not conn_manager.send_data(pcm[offset:offset + chunk_size], wait=True):
            return False
        time.sleep(0.005)
    return True


def _capture_speech_segment(p, noise_floor):
    pipeline_config = AudioPipelineConfig.from_app_config(noise_floor)
    pipeline = EndpointingAudioPipeline(pipeline_config)
    channels = config["audio"]["channels"]

    with suppress_alsa_stderr():
        mic_stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=pipeline_config.sample_rate,
            input=True,
            frames_per_buffer=pipeline.frame_samples,
        )

    try:
        while True:
            data = mic_stream.read(pipeline.frame_samples, exception_on_overflow=False)
            result = pipeline.process_frame(data)
            status = "RECORDING" if pipeline.is_recording else "LISTENING"

            print_audio_meter(
                result.decision.rms,
                result.decision.energy_threshold,
                result.decision.is_speech or pipeline.is_recording,
                status,
            )

            if result.segment is not None:
                print(f"\n✅ Speech captured ({result.segment.duration_ms / 1000:.2f}s)")
                return result.segment

            if pipeline.timed_out():
                print("\n💤 Session Timeout.")
                return None
    finally:
        mic_stream.stop_stream()
        mic_stream.close()


def _play_response(p, conn_manager, session_state):
    thinking_event = threading.Event()
    thinking_event.set()
    pending_action_payload = None
    keep_session_open = False

    with suppress_alsa_stderr():
        speaker_stream = p.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=24000,
            output=True,
        )

    voice_stream_active = True
    first_audio_received = False

    try:
        while True:
            try:
                opcode, data = conn_manager.recv_data()

                if opcode == 2:
                    if not first_audio_received:
                        first_audio_received = True
                        thinking_event.clear()
                        session_state.responding()
                        print("🤖 Volco Speaking...")
                    if voice_stream_active:
                        stereo_data = audioop.tostereo(data, 2, 1, 1)
                        speaker_stream.write(stereo_data)

                elif opcode == 1:
                    msg = data
                    if msg == "NO_SPEECH":
                        thinking_event.clear()
                        print("\n🔇 Server rejected segment as no speech.")
                        break
                    if msg == "END_OF_RESPONSE":
                        break
                    if msg in {"CONTINUE_SESSION", "KEEP_SESSION_OPEN", "FOLLOW_UP"}:
                        keep_session_open = True
                        break
                    if msg in {"END_SESSION", "SESSION_END", "CLOSE_SESSION"}:
                        keep_session_open = False
                        break

                    if isinstance(msg, str) and msg.startswith("{"):
                        try:
                            payload = json.loads(msg)
                            action = payload.get("action")
                            if action == "local_intent_request":
                                result = assistant_processor.process_user_input(
                                    payload.get("text", ""),
                                    user_id=payload.get("user_id", "default"),
                                )
                                conn_manager.send_data(json.dumps({
                                    "action": "local_intent_result",
                                    "request_id": payload.get("request_id"),
                                    "result": result,
                                }), wait=True)
                                continue
                            if payload.get("keep_session_open") is True or payload.get("continue_session") is True:
                                keep_session_open = True
                            if payload.get("end_session") is True:
                                keep_session_open = False
                            if action and action != "none":
                                pending_action_payload = payload
                            continue
                        except Exception:
                            pass

            except Exception as e:
                print(f"❌ Playback Error: {e}")
                keep_session_open = False
                break
    finally:
        thinking_event.clear()

        if voice_stream_active:
            speaker_stream.stop_stream()
            speaker_stream.close()

    return keep_session_open, pending_action_payload


def _execute_deferred_action(pending_action_payload):
    print("🎬 Executing deferred action...")
    action = pending_action_payload.get("action")
    query = pending_action_payload.get("query", "").rstrip(".!?,")
    level = pending_action_payload.get("level")

    if action == "spotify_play_track":
        spotify.search_and_play(query, "track")
    elif action == "spotify_next":
        spotify.control_playback("next")
    elif action == "spotify_previous":
        spotify.control_playback("previous")
    elif action == "spotify_pause":
        spotify.control_playback("pause")
    elif action == "spotify_resume":
        spotify.control_playback("resume")
    elif action == "spotify_play_album":
        spotify.search_and_play(query, "album")
    elif action == "spotify_play_playlist":
        spotify.search_and_play(query, "playlist")
    elif action == "spotify_set_volume":
        if isinstance(level, int):
            spotify.set_volume(level)
    elif action == "spotify_get_volume":
        current_volume = spotify.get_current_volume()
        if current_volume is not None:
            print(f"🎵 Current Volco volume: {current_volume}%")
    elif action == "device_control":
        command = pending_action_payload.get("command", "control")
        device = pending_action_payload.get("device", "device")
        print(f"🏠 Device control requested: {command} {device}")

    print("\n🎵 Music mode active. Returning to Wake Word listener...")


def start_ai_session(wake_engine, conn_manager, noise_floor):
    """Keeps a wake-word-triggered AI conversation open until it naturally ends."""
    
    with suppress_alsa_stderr():
        p = pyaudio.PyAudio()

    session_state = VoiceSessionStateMachine()
    session_state.wake_word_detected()
    print(f"\n🧠 [AI MODE] VAD Endpointing Active (Initial Floor: {noise_floor})")

    try:
        if not conn_manager.is_connected():
            session_state.reset_to_idle("not_connected")
            return

        while True:
            session_state.start_listening()
            segment = _capture_speech_segment(p, noise_floor)
            if segment is None:
                conn_manager.send_data("CLEAR")
                play_sfx(config["audio"]["session_end"], async_play=True)
                session_state.reset_to_idle("timeout_or_noise")
                break

            if not conn_manager.is_connected():
                session_state.reset_to_idle("connection_lost")
                break

            if not conn_manager.send_data("CLEAR"):
                session_state.reset_to_idle("clear_failed")
                break

            if not _send_audio_segment(conn_manager, segment.pcm):
                session_state.reset_to_idle("upload_failed")
                break

            session_state.processing_asr()
            print("🚀 Sending COMMIT...")
            if not conn_manager.send_data("COMMIT", wait=True):
                session_state.reset_to_idle("commit_failed")
                break

            print("🧠 Vella is processing... (Waiting for response)")
            keep_session_open, pending_action_payload = _play_response(p, conn_manager, session_state)

            if pending_action_payload:
                _execute_deferred_action(pending_action_payload)
                session_state.reset_to_idle("deferred_action")
                break

            if not keep_session_open:
                session_state.reset_to_idle("server_closed_session")
                break

            print("\n🎤 Conversation still open. Listening for your next reply...")

        return

    except Exception as e:
        print(f"⚠️ Session Error: {e}")
        session_state.reset_to_idle("error")
    finally:
        p.terminate()
