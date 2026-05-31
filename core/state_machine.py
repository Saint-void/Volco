import logging
from enum import Enum


logger = logging.getLogger("volco.voice")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class VoiceState(str, Enum):
    IDLE = "IDLE"
    WAKE_WORD_DETECTED = "WAKE_WORD_DETECTED"
    LISTENING = "LISTENING"
    PROCESSING_ASR = "PROCESSING_ASR"
    RESPONDING = "RESPONDING"
    RESET_TO_IDLE = "RESET_TO_IDLE"


def log_voice_event(event: str, **fields):
    details = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    logger.info("%s%s", event, f" {details}" if details else "")


class VoiceSessionStateMachine:
    def __init__(self):
        self.state = VoiceState.IDLE

    def transition(self, next_state: VoiceState, event: str):
        previous = self.state
        self.state = next_state
        log_voice_event(
            "state_transition",
            event=event,
            from_state=previous.value,
            to_state=next_state.value,
        )

    def wake_word_detected(self):
        self.transition(VoiceState.WAKE_WORD_DETECTED, "wake_word_detected")

    def start_listening(self):
        self.transition(VoiceState.LISTENING, "start_listening")

    def processing_asr(self):
        self.transition(VoiceState.PROCESSING_ASR, "asr_started")
        log_voice_event("asr_started")

    def responding(self):
        self.transition(VoiceState.RESPONDING, "response_started")

    def reset_to_idle(self, reason: str = "complete"):
        self.transition(VoiceState.RESET_TO_IDLE, "reset_requested")
        self.transition(VoiceState.IDLE, "session_reset")
        log_voice_event("session_reset", reason=reason)
