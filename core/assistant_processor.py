from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.intent_detector import IntentDetector
from core.memory_manager import MemoryManager
from core.models import Intent, ProcessedInput


logger = logging.getLogger("volco.assistant")


class AssistantProcessor:
    def __init__(self, memory_manager: MemoryManager | None = None, detector: IntentDetector | None = None):
        self.memory = memory_manager or MemoryManager()
        self.detector = detector or IntentDetector()

    def process_user_input(self, text: str, user_id: str = "default") -> dict[str, Any]:
        result = self.detector.detect(text)
        entities = dict(result.entities)

        if result.intent == Intent.STORE_MEMORY:
            key = str(entities.get("key", "")).strip()
            value = str(entities.get("value", "")).strip()
            if key and value:
                self.memory.store_memory(user_id, key, value, source_text=text)
                return ProcessedInput(
                    intent=result.intent,
                    entities=entities,
                    response=self._store_response(key, value),
                    should_call_llm=False,
                ).to_dict()
            return ProcessedInput(result.intent, entities, "I heard that, but I could not find what to remember.").to_dict()

        if result.intent == Intent.RECALL_MEMORY:
            key = str(entities.get("key", "")).strip()
            value = self.memory.recall_memory(user_id, key) if key else None
            return ProcessedInput(
                intent=result.intent,
                entities={**entities, "value": value} if value else entities,
                response=self._recall_response(key, value),
                should_call_llm=False,
            ).to_dict()

        if result.intent == Intent.PLAY_MUSIC:
            return ProcessedInput(
                intent=result.intent,
                entities=entities,
                response=self._music_response(entities),
                should_call_llm=False,
            ).to_dict()

        if result.intent == Intent.STOP_MUSIC:
            return ProcessedInput(
                intent=result.intent,
                entities=entities,
                response="Certainly. Pausing your music.",
                should_call_llm=False,
            ).to_dict()

        if result.intent == Intent.SET_VOLUME:
            level = entities.get("level")
            return ProcessedInput(
                intent=result.intent,
                entities=entities,
                response=f"Setting the volume to {level} percent.",
                should_call_llm=False,
            ).to_dict()

        if result.intent == Intent.GET_VOLUME:
            return ProcessedInput(
                intent=result.intent,
                entities=entities,
                response="Checking the current volume.",
                should_call_llm=False,
            ).to_dict()

        if result.intent == Intent.DEVICE_CONTROL:
            device = entities.get("device", "that device")
            action = entities.get("action", "control")
            return ProcessedInput(
                intent=result.intent,
                entities=entities,
                response=f"Okay. I will {action} {device}.",
                should_call_llm=False,
            ).to_dict()

        return ProcessedInput(Intent.GENERAL_CHAT, entities, "", should_call_llm=True).to_dict()

    @staticmethod
    def _store_response(key: str, value: str) -> str:
        if key == "name":
            return f"I'll remember your name is {value}."
        if key == "city":
            return f"I'll remember that you live in {value}."
        if key == "note":
            return f"I'll remember that {value}."
        return f"I'll remember your {key.replace('_', ' ')} is {value}."

    @staticmethod
    def _recall_response(key: str, value: str | None) -> str:
        if not value:
            return "I don't have that in memory yet."
        if key == "name":
            return f"Your name is {value}."
        if key == "city":
            return f"You live in {value}."
        if key.startswith("favorite_"):
            return f"Your {key.replace('_', ' ')} is {value}."
        return f"I remember: {value}."

    @staticmethod
    def _music_response(entities: dict[str, Any]) -> str:
        action = entities.get("action")
        query = str(entities.get("query", "")).strip()
        if action == "spotify_resume":
            return "Certainly. Resuming your music on Spotify."
        if query:
            return f"Certainly. Playing {query} for you."
        return "Certainly. Playing music for you."


_default_processor: AssistantProcessor | None = None


def get_assistant_processor(db_path: str | Path | None = None) -> AssistantProcessor:
    global _default_processor
    if _default_processor is None or db_path is not None:
        _default_processor = AssistantProcessor(memory_manager=MemoryManager(db_path=db_path))
    return _default_processor


def process_user_input(text: str, user_id: str = "default") -> dict[str, Any]:
    return get_assistant_processor().process_user_input(text, user_id=user_id)
