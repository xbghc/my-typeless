
import sys
import os
import time
import unittest
import threading
from unittest.mock import MagicMock, patch

# Ensure src is in path
sys.path.insert(0, os.path.abspath("src"))

# Apply mocks
import tests_repro.mock_modules

# Now import app modules
from my_typeless.config import AppConfig
from my_typeless.worker import Worker

class TestWorkerClientReuse(unittest.TestCase):
    @patch("my_typeless.worker.STTClient")
    @patch("my_typeless.worker.LLMClient")
    @patch("my_typeless.worker.inject_text")
    def test_clients_recreated_currently(self, mock_inject, mock_llm_cls, mock_stt_cls):
        # Setup mocks
        mock_stt_instance = mock_stt_cls.return_value
        # Mock transcribe to return a non-empty string so processing continues
        mock_stt_instance.transcribe.return_value = "hello"

        mock_llm_instance = mock_llm_cls.return_value
        mock_llm_instance.refine.return_value = "Hello."

        config = AppConfig()
        worker = Worker(config)

        # Mock recorder
        worker._recorder = MagicMock()
        worker._recorder.stop.return_value = b""

        # Event to wait for idle state
        idle_event = threading.Event()
        def on_state_changed(state):
            if state == "idle":
                idle_event.set()

        worker.events.on("state_changed", on_state_changed)

        print("--- Session 1 ---")
        worker.start_recording()
        # Simulate segment
        worker._on_segment(b"chunk1")
        worker.stop_recording_and_process()

        # Wait for processing to finish
        if not idle_event.wait(timeout=2.0):
            self.fail("Timeout waiting for idle state (Session 1)")
        idle_event.clear()

        print("--- Session 2 ---")
        worker.start_recording()
        worker._on_segment(b"chunk2")
        worker.stop_recording_and_process()

        if not idle_event.wait(timeout=2.0):
            self.fail("Timeout waiting for idle state (Session 2)")

        # Assertions
        print(f"STTClient call count: {mock_stt_cls.call_count}")
        print(f"LLMClient call count: {mock_llm_cls.call_count}")

        # Expectation: Clients are instantiated only ONCE
        self.assertEqual(mock_stt_cls.call_count, 1)
        self.assertEqual(mock_llm_cls.call_count, 1)

if __name__ == "__main__":
    unittest.main()
