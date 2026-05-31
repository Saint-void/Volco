import tempfile
import unittest
from pathlib import Path

from core.assistant_processor import AssistantProcessor
from core.intent_detector import IntentDetector
from core.memory_manager import MemoryManager


class IntentDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = IntentDetector()

    def test_store_name(self):
        result = self.detector.detect("My name is Donald")
        self.assertEqual(result.intent.value, "STORE_MEMORY")
        self.assertEqual(result.entities, {"key": "name", "value": "Donald"})

    def test_store_city(self):
        result = self.detector.detect("Remember that I live in Lagos")
        self.assertEqual(result.intent.value, "STORE_MEMORY")
        self.assertEqual(result.entities, {"key": "city", "value": "Lagos"})

    def test_recall_name(self):
        result = self.detector.detect("What is my name?")
        self.assertEqual(result.intent.value, "RECALL_MEMORY")
        self.assertEqual(result.entities, {"key": "name"})

    def test_play_music(self):
        result = self.detector.detect("Can you play NF")
        self.assertEqual(result.intent.value, "PLAY_MUSIC")
        self.assertEqual(result.entities["action"], "spotify_play_track")
        self.assertEqual(result.entities["query"], "nf")

    def test_set_volume(self):
        result = self.detector.detect("Set volume to 50 percent")
        self.assertEqual(result.intent.value, "SET_VOLUME")
        self.assertEqual(result.entities["level"], 50)


class AssistantProcessorTests(unittest.TestCase):
    def make_processor(self):
        tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(tmpdir.name) / "memory.sqlite3"
        processor = AssistantProcessor(memory_manager=MemoryManager(db_path=db_path))
        return tmpdir, processor

    def test_store_and_recall_name_without_llm(self):
        tmpdir, processor = self.make_processor()
        self.addCleanup(tmpdir.cleanup)

        stored = processor.process_user_input("My name is Donald", user_id="user-1")
        self.assertEqual(stored["intent"], "STORE_MEMORY")
        self.assertFalse(stored["should_call_llm"])

        recalled = processor.process_user_input("What is my name?", user_id="user-1")
        self.assertEqual(recalled["intent"], "RECALL_MEMORY")
        self.assertEqual(recalled["response"], "Your name is Donald.")
        self.assertFalse(recalled["should_call_llm"])

    def test_general_chat_calls_llm(self):
        tmpdir, processor = self.make_processor()
        self.addCleanup(tmpdir.cleanup)

        result = processor.process_user_input("Tell me a story", user_id="user-1")
        self.assertEqual(result["intent"], "GENERAL_CHAT")
        self.assertTrue(result["should_call_llm"])


if __name__ == "__main__":
    unittest.main()
