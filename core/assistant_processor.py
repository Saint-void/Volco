from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.memory_manager import MemoryManager
from core.models import Intent, ProcessedInput


logger = logging.getLogger("volco.assistant")


class AssistantProcessor:
    def __init__(self, memory_manager: MemoryManager | None = None):
        # Local intent detection removed. Keep memory manager for compatibility.
        self.memory = memory_manager or MemoryManager()

    def process_user_input(self, text: str, user_id: str = "default") -> dict[str, Any]:
        # Intent detection and local action handling removed. Always treat as general chat.
        entities: dict[str, Any] = {}
        return ProcessedInput(Intent.GENERAL_CHAT, entities, "", should_call_llm=True).to_dict()


# Backwards-compatible factory
_default_processor: AssistantProcessor | None = None


def get_assistant_processor(db_path: str | Path | None = None) -> AssistantProcessor:
    global _default_processor
    if _default_processor is None or db_path is not None:
        _default_processor = AssistantProcessor(memory_manager=MemoryManager(db_path=db_path))
    return _default_processor


def process_user_input(text: str, user_id: str = "default") -> dict[str, Any]:
    return get_assistant_processor().process_user_input(text, user_id=user_id)
