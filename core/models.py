from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Intent(str, Enum):
    STORE_MEMORY = "STORE_MEMORY"
    RECALL_MEMORY = "RECALL_MEMORY"
    PLAY_MUSIC = "PLAY_MUSIC"
    STOP_MUSIC = "STOP_MUSIC"
    SET_VOLUME = "SET_VOLUME"
    GET_VOLUME = "GET_VOLUME"
    DEVICE_CONTROL = "DEVICE_CONTROL"
    GENERAL_CHAT = "GENERAL_CHAT"


@dataclass(frozen=True)
class IntentResult:
    intent: Intent
    entities: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass(frozen=True)
class ProcessedInput:
    intent: Intent
    entities: dict[str, Any] = field(default_factory=dict)
    response: str = ""
    should_call_llm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "entities": self.entities,
            "response": self.response,
            "should_call_llm": self.should_call_llm,
        }
