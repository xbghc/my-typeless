
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# Mock dependencies before importing application modules
sys.modules["pyaudio"] = MagicMock()
sys.modules["win32clipboard"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["win32gui"] = MagicMock()
sys.modules["win32api"] = MagicMock()
sys.modules["keyboard"] = MagicMock()
sys.modules["openai"] = MagicMock()

# Now import the module under test
from my_typeless.worker import Worker
from my_typeless.config import AppConfig

class TestWorker(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock(spec=AppConfig)
        self.config.stt = MagicMock()
        self.config.llm = MagicMock()
        self.config.build_stt_prompt.return_value = "stt_prompt"
        self.config.build_llm_system_prompt.return_value = "llm_prompt"

        # Patch internal dependencies of Worker
        self.recorder_patcher = patch("my_typeless.worker.Recorder")
        self.stt_client_patcher = patch("my_typeless.worker.STTClient")
        self.llm_client_patcher = patch("my_typeless.worker.LLMClient")
        self.inject_text_patcher = patch("my_typeless.worker.inject_text")
        self.add_history_patcher = patch("my_typeless.worker.add_history")

        self.mock_recorder_cls = self.recorder_patcher.start()
        self.mock_stt_cls = self.stt_client_patcher.start()
        self.mock_llm_cls = self.llm_client_patcher.start()
        self.mock_inject = self.inject_text_patcher.start()
        self.mock_add_history = self.add_history_patcher.start()

        self.mock_recorder = self.mock_recorder_cls.return_value
        # Mock stop to return empty bytes by default
        self.mock_recorder.stop.return_value = b""

        self.mock_stt = self.mock_stt_cls.return_value
        self.mock_llm = self.mock_llm_cls.return_value

    def tearDown(self):
        self.recorder_patcher.stop()
        self.stt_client_patcher.stop()
        self.llm_client_patcher.stop()
        self.inject_text_patcher.stop()
        self.add_history_patcher.stop()

    def test_end_to_end_flow(self):
        worker = Worker(self.config)

        # Setup mocks behavior
        self.mock_stt.transcribe.side_effect = ["raw1", "raw2"]
        self.mock_llm.refine.side_effect = ["refined1", "refined2"]

        # Use an event to wait for completion
        done_event = threading.Event()
        def on_state_changed(state):
            if state == "idle":
                done_event.set()

        worker.events.on("state_changed", on_state_changed)

        # Start recording
        worker.start_recording()

        # Simulate audio segments
        worker._on_segment(b"audio1")
        worker._on_segment(b"audio2")

        # Stop recording
        worker.stop_recording_and_process()

        # Wait for processing to finish (timeout 2s)
        completed = done_event.wait(2.0)
        self.assertTrue(completed, "Worker did not finish processing in time")

        # Verify STT calls
        self.assertEqual(self.mock_stt.transcribe.call_count, 2)

        # Verify LLM calls
        self.assertEqual(self.mock_llm.refine.call_count, 2)

        # Verify Injection
        # Should be "refined1" + "refined2"
        self.mock_inject.assert_called_once_with("refined1refined2")

        # Verify History
        self.mock_add_history.assert_called_once()
        args, kwargs = self.mock_add_history.call_args
        self.assertEqual(args[0], "raw1raw2")
        self.assertEqual(args[1], "refined1refined2")

if __name__ == "__main__":
    unittest.main()
