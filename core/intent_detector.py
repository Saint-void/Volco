from __future__ import annotations

import logging
import re
from typing import Match

from core.models import Intent, IntentResult


logger = logging.getLogger("volco.intent")


def _clean_value(value: str) -> str:
    value = re.sub(r"\b(for me|please|now|on spotify|with spotify)\b", "", value, flags=re.I)
    return value.strip(" .,!?'\"")


def _title_value(value: str) -> str:
    cleaned = _clean_value(value)
    if not cleaned:
        return cleaned
    if cleaned.isupper():
        return cleaned
    return " ".join(word.capitalize() if word.islower() else word for word in cleaned.split())


class IntentDetector:
    """Small offline rule-based detector designed for low-power devices."""

    _store_patterns: tuple[tuple[str, str], ...] = (
        (r"^my\s+name\s+is\s+(.+)$", "name"),
        (r"^i\s+am\s+called\s+(.+)$", "name"),
        (r"^call\s+me\s+(.+)$", "name"),
        (r"^remember\s+that\s+my\s+name\s+is\s+(.+)$", "name"),
        (r"^remember\s+that\s+i\s+live\s+in\s+(.+)$", "city"),
        (r"^i\s+live\s+in\s+(.+)$", "city"),
        (r"^remember\s+that\s+i\s+am\s+from\s+(.+)$", "city"),
        (r"^i\s+am\s+from\s+(.+)$", "city"),
        (r"^my\s+favorite\s+color\s+is\s+(.+)$", "favorite_color"),
        (r"^remember\s+that\s+my\s+favorite\s+color\s+is\s+(.+)$", "favorite_color"),
        (r"^my\s+favorite\s+song\s+is\s+(.+)$", "favorite_song"),
        (r"^my\s+favorite\s+artist\s+is\s+(.+)$", "favorite_artist"),
        (r"^remember\s+that\s+(.+)$", "note"),
    )

    _recall_patterns: tuple[tuple[str, str], ...] = (
        (r"^(?:what|who)\s+is\s+my\s+name\??$", "name"),
        (r"^what\s+am\s+i\s+called\??$", "name"),
        (r"^where\s+do\s+i\s+live\??$", "city"),
        (r"^where\s+am\s+i\s+from\??$", "city"),
        (r"^what\s+is\s+my\s+favorite\s+color\??$", "favorite_color"),
        (r"^what\s+is\s+my\s+favorite\s+song\??$", "favorite_song"),
        (r"^who\s+is\s+my\s+favorite\s+artist\??$", "favorite_artist"),
        (r"^what\s+did\s+i\s+ask\s+you\s+to\s+remember\??$", "note"),
        (r"^do\s+you\s+remember\s+(.+)\??$", "note"),
    )

    _music_patterns: tuple[str, ...] = (
        r"^(?:please\s+)?play\s+(.+)$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?play\s+(.+)$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?put\s+on\s+(.+)$",
        r"^(?:please\s+)?put\s+on\s+(.+)$",
        r"^(?:please\s+)?start\s+playing\s+(.+)$",
        r"^i\s+(?:want|wanna|would\s+like)\s+to\s+(?:listen\s+to|hear|play)\s+(.+)$",
        r"^let'?s\s+(?:listen\s+to|hear|play)\s+(.+)$",
    )

    def detect(self, text: str) -> IntentResult:
        original = text.strip()
        normalized = re.sub(r"\s+", " ", original.lower()).strip()

        if not normalized:
            return IntentResult(Intent.GENERAL_CHAT)

        result = self._detect_store_memory(original, normalized)
        if result:
            return result

        result = self._detect_recall_memory(normalized)
        if result:
            return result

        result = self._detect_volume(normalized)
        if result:
            return result

        result = self._detect_music(normalized)
        if result:
            return result

        result = self._detect_device_control(normalized)
        if result:
            return result

        return IntentResult(Intent.GENERAL_CHAT, confidence=0.0)

    def _detect_store_memory(self, original: str, normalized: str) -> IntentResult | None:
        for pattern, key in self._store_patterns:
            match = re.match(pattern, normalized)
            if match:
                value = self._extract_original_group(original, match)
                if key == "note":
                    value = _clean_value(value)
                else:
                    value = _title_value(value)
                return IntentResult(Intent.STORE_MEMORY, {"key": key, "value": value})
        return None

    def _detect_recall_memory(self, normalized: str) -> IntentResult | None:
        for pattern, key in self._recall_patterns:
            if re.match(pattern, normalized):
                return IntentResult(Intent.RECALL_MEMORY, {"key": key})
        return None

    def _detect_music(self, normalized: str) -> IntentResult | None:
        if normalized in {"play", "play music", "resume", "resume music", "continue music"}:
            return IntentResult(Intent.PLAY_MUSIC, {"action": "spotify_resume", "query": ""})

        if any(phrase in normalized for phrase in ("stop music", "stop the music", "pause music", "pause the music")):
            return IntentResult(Intent.STOP_MUSIC, {"action": "spotify_pause"})

        for pattern in self._music_patterns:
            match = re.match(pattern, normalized)
            if not match:
                continue
            query = _clean_value(match.group(1))
            if query in {"music", "some music", "my music"}:
                return IntentResult(Intent.PLAY_MUSIC, {"action": "spotify_resume", "query": ""})
            search_type = "track"
            if "album" in query:
                search_type = "album"
                query = _clean_value(query.replace("album", ""))
            elif "playlist" in query:
                search_type = "playlist"
                query = _clean_value(query.replace("playlist", ""))
            return IntentResult(
                Intent.PLAY_MUSIC,
                {"action": f"spotify_play_{search_type}", "query": query, "search_type": search_type},
            )

        return None

    def _detect_volume(self, normalized: str) -> IntentResult | None:
        if re.search(r"\b(?:what|what's|get|current)\b.*\bvolume\b", normalized):
            return IntentResult(Intent.GET_VOLUME, {"action": "spotify_get_volume"})

        match = re.search(r"\b(?:set|change|turn)\s+(?:the\s+)?volume\s+(?:to\s+)?(\d{1,3})\s*(?:percent|%)?\b", normalized)
        if match:
            level = max(0, min(100, int(match.group(1))))
            return IntentResult(Intent.SET_VOLUME, {"action": "spotify_set_volume", "level": level})

        return None

    def _detect_device_control(self, normalized: str) -> IntentResult | None:
        match = re.match(r"^(?:turn|switch)\s+(on|off)\s+(?:the\s+)?(.+)$", normalized)
        if match:
            return IntentResult(Intent.DEVICE_CONTROL, {"action": match.group(1), "device": _clean_value(match.group(2))})
        return None

    @staticmethod
    def _extract_original_group(original: str, normalized_match: Match[str]) -> str:
        start, end = normalized_match.span(1)
        return original[start:end]
