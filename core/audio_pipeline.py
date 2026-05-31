import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

from config.config_manager import config as app_config
from core.state_machine import log_voice_event
from core.vad import VADConfig, VADDecision, VoiceActivityDetector


@dataclass
class AudioSegment:
    pcm: bytes
    sample_rate: int
    duration_ms: int
    peak_rms: int


@dataclass
class FrameResult:
    decision: VADDecision
    segment: Optional[AudioSegment] = None


@dataclass
class AudioPipelineConfig:
    sample_rate: int = 16000
    frame_duration_ms: int = 30
    endpoint_silence_ms: int = 1000
    pre_roll_ms: int = 240
    trailing_padding_ms: int = 180
    min_speech_ms: int = 500
    max_utterance_ms: int = 12000
    session_timeout_ms: int = 5000
    speech_trigger_frames: int = 3
    vad_aggressiveness: int = 2
    min_energy: int = 350
    energy_ratio: float = 1.8
    noise_floor: int = 100

    @classmethod
    def from_app_config(cls, noise_floor: int):
        audio = app_config["audio"]
        endpoint_ms = audio.get("endpoint_silence_ms")
        if endpoint_ms is None:
            endpoint_ms = int(audio.get("silence_limit", 1.0) * 1000)
        endpoint_ms = max(800, min(1200, int(endpoint_ms)))
        min_energy = max(
            audio.get("min_energy", 350),
            noise_floor + audio.get("safety_margin", 300),
        )

        return cls(
            sample_rate=audio.get("rate", 16000),
            frame_duration_ms=audio.get("vad_frame_ms", 30),
            endpoint_silence_ms=endpoint_ms,
            pre_roll_ms=audio.get("pre_roll_ms", 240),
            trailing_padding_ms=audio.get("trailing_padding_ms", 180),
            min_speech_ms=int(audio.get("min_speech_duration", 0.5) * 1000),
            max_utterance_ms=audio.get("max_utterance_ms", 12000),
            session_timeout_ms=int(audio.get("session_timeout", 5.0) * 1000),
            speech_trigger_frames=audio.get("speech_trigger_frames", 3),
            vad_aggressiveness=audio.get("vad_aggressiveness", 2),
            min_energy=min_energy,
            energy_ratio=audio.get("energy_ratio", 1.8),
            noise_floor=noise_floor,
        )


class EndpointingAudioPipeline:
    def __init__(self, config: AudioPipelineConfig):
        self.config = config
        self.vad = VoiceActivityDetector(
            VADConfig(
                sample_rate=config.sample_rate,
                frame_duration_ms=config.frame_duration_ms,
                aggressiveness=config.vad_aggressiveness,
                min_energy=config.min_energy,
                energy_ratio=config.energy_ratio,
                noise_floor=config.noise_floor,
            )
        )
        self.frame_samples = self.vad.frame_samples
        self.frame_bytes = self.vad.frame_bytes
        self._pre_roll_frames = max(1, int(config.pre_roll_ms / config.frame_duration_ms))
        self._pre_roll = deque(maxlen=self._pre_roll_frames)
        self.reset()

    @property
    def is_recording(self) -> bool:
        return self._speech_started

    def reset(self):
        self._segment = bytearray()
        self._speech_started = False
        self._consecutive_speech = 0
        self._silence_ms = 0
        self._speech_ms = 0
        self._last_voice_len = 0
        self._peak_rms = 0
        self._listen_started_at = time.monotonic()
        self._speech_started_at = None
        self._pre_roll.clear()

    def timed_out(self) -> bool:
        if self._speech_started:
            return False
        elapsed_ms = int((time.monotonic() - self._listen_started_at) * 1000)
        return elapsed_ms >= self.config.session_timeout_ms

    def process_frame(self, pcm_frame: bytes) -> FrameResult:
        if len(pcm_frame) != self.frame_bytes:
            pcm_frame = self._normalize_frame_size(pcm_frame)

        decision = self.vad.is_speech(pcm_frame)
        self._peak_rms = max(self._peak_rms, decision.rms)
        if not self._speech_started:
            self._pre_roll.append(pcm_frame)

        if decision.is_speech:
            self._consecutive_speech += 1
            self._silence_ms = 0

            if not self._speech_started and self._consecutive_speech >= self.config.speech_trigger_frames:
                self._speech_started = True
                self._speech_started_at = time.monotonic()
                self._segment.extend(b"".join(self._pre_roll))
                self._speech_ms = self.config.speech_trigger_frames * self.config.frame_duration_ms
                self._last_voice_len = len(self._segment)
                log_voice_event(
                    "speech_started",
                    rms=decision.rms,
                    threshold=decision.energy_threshold,
                )
            elif self._speech_started:
                self._segment.extend(pcm_frame)
                self._speech_ms += self.config.frame_duration_ms
                self._last_voice_len = len(self._segment)
        else:
            self._consecutive_speech = 0
            if self._speech_started:
                self._silence_ms += self.config.frame_duration_ms
                self._segment.extend(pcm_frame)

        segment = self._maybe_endpoint()
        return FrameResult(decision=decision, segment=segment)

    def force_endpoint(self) -> Optional[AudioSegment]:
        if not self._speech_started:
            return None
        return self._finalize_segment(reason="forced")

    def _maybe_endpoint(self) -> Optional[AudioSegment]:
        if not self._speech_started:
            return None

        if self._silence_ms >= self.config.endpoint_silence_ms:
            return self._finalize_segment(reason="silence")

        if self._speech_ms >= self.config.max_utterance_ms:
            return self._finalize_segment(reason="max_utterance")

        return None

    def _finalize_segment(self, reason: str) -> Optional[AudioSegment]:
        keep_padding = int(self.config.trailing_padding_ms / self.config.frame_duration_ms) * self.frame_bytes
        end_at = min(len(self._segment), self._last_voice_len + keep_padding)
        pcm = bytes(self._segment[:end_at])
        duration_ms = int(len(pcm) / 2 / self.config.sample_rate * 1000)

        log_voice_event("speech_ended", duration_ms=duration_ms, reason=reason)

        if duration_ms < self.config.min_speech_ms:
            log_voice_event(
                "noise_filtered",
                reason="too_short",
                duration_ms=duration_ms,
                min_speech_ms=self.config.min_speech_ms,
            )
            self.reset()
            return None

        segment = AudioSegment(
            pcm=pcm,
            sample_rate=self.config.sample_rate,
            duration_ms=duration_ms,
            peak_rms=self._peak_rms,
        )
        log_voice_event(
            "endpoint_triggered",
            duration_ms=duration_ms,
            bytes=len(pcm),
            peak_rms=self._peak_rms,
        )
        self.reset()
        return segment

    def _normalize_frame_size(self, pcm_frame: bytes) -> bytes:
        if len(pcm_frame) > self.frame_bytes:
            return pcm_frame[: self.frame_bytes]
        return pcm_frame + (b"\x00" * (self.frame_bytes - len(pcm_frame)))
