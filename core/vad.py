import audioop
from dataclasses import dataclass

from core.state_machine import log_voice_event

try:
    import webrtcvad
except ImportError:  # pragma: no cover - exercised on devices before dependency install
    webrtcvad = None


@dataclass
class VADConfig:
    sample_rate: int = 16000
    frame_duration_ms: int = 30
    aggressiveness: int = 2
    min_energy: int = 350
    energy_ratio: float = 1.8
    noise_floor: int = 100
    noise_alpha: float = 0.02
    noise_log_interval_ms: int = 1000


@dataclass
class VADDecision:
    is_speech: bool
    rms: int
    energy_threshold: int
    vad_speech: bool
    energy_ok: bool


class VoiceActivityDetector:
    """
    Low-CPU WebRTC VAD with an adaptive energy gate.

    WebRTC VAD catches speech-like structure; the RMS gate prevents constant fan,
    HVAC, and electrical noise from keeping the assistant alive.
    """

    def __init__(self, config: VADConfig):
        self.config = config
        self.noise_floor = max(float(config.noise_floor), 1.0)
        self.frame_index = 0
        self._last_noise_log_frame = -10_000

        self._vad = None
        if webrtcvad is not None:
            self._vad = webrtcvad.Vad(config.aggressiveness)
        else:
            log_voice_event("vad_fallback", reason="webrtcvad_not_installed")

    @property
    def frame_samples(self) -> int:
        return int(self.config.sample_rate * self.config.frame_duration_ms / 1000)

    @property
    def frame_bytes(self) -> int:
        return self.frame_samples * 2

    def is_speech(self, pcm_frame: bytes) -> VADDecision:
        self.frame_index += 1
        rms = audioop.rms(pcm_frame, 2) if pcm_frame else 0
        energy_threshold = max(
            self.config.min_energy,
            int(self.noise_floor * self.config.energy_ratio),
        )
        energy_ok = rms >= energy_threshold

        vad_speech = energy_ok
        if self._vad is not None and len(pcm_frame) == self.frame_bytes:
            try:
                vad_speech = self._vad.is_speech(pcm_frame, self.config.sample_rate)
            except Exception:
                vad_speech = False

        speech = bool(vad_speech and energy_ok)

        if not speech:
            self._update_noise_floor(rms)
            self._log_noise_filtered(rms, energy_threshold, vad_speech, energy_ok)

        return VADDecision(
            is_speech=speech,
            rms=rms,
            energy_threshold=energy_threshold,
            vad_speech=vad_speech,
            energy_ok=energy_ok,
        )

    def _update_noise_floor(self, rms: int):
        if rms <= max(self.noise_floor * 1.8, self.config.min_energy):
            alpha = self.config.noise_alpha
            self.noise_floor = (1.0 - alpha) * self.noise_floor + alpha * max(rms, 1)

    def _log_noise_filtered(self, rms: int, threshold: int, vad_speech: bool, energy_ok: bool):
        frames_between_logs = max(
            1,
            int(self.config.noise_log_interval_ms / self.config.frame_duration_ms),
        )
        if self.frame_index - self._last_noise_log_frame >= frames_between_logs:
            self._last_noise_log_frame = self.frame_index
            log_voice_event(
                "noise_filtered",
                rms=rms,
                threshold=threshold,
                vad_speech=vad_speech,
                energy_ok=energy_ok,
            )
