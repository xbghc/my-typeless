import sys
import unittest
from unittest.mock import MagicMock, patch
import time
import threading

# Mock platform-specific modules before importing worker
sys.modules["pyaudio"] = MagicMock()
sys.modules["keyboard"] = MagicMock()
sys.modules["win32clipboard"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["win32gui"] = MagicMock()
sys.modules["win32api"] = MagicMock()
sys.modules["openai"] = MagicMock()

# Import worker after mocking
from my_typeless.worker import Worker
from my_typeless.config import AppConfig

class TestWorkerLogic(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock(spec=AppConfig)
        self.config.stt = MagicMock()
        self.config.llm = MagicMock()
        self.config.build_stt_prompt.return_value = ""
        self.config.build_llm_system_prompt.return_value = ""

        # Patch Recorder
        patcher = patch("my_typeless.worker.Recorder")
        self.MockRecorder = patcher.start()
        self.mock_recorder = self.MockRecorder.return_value
        self.mock_recorder.start = MagicMock()
        self.mock_recorder.stop = MagicMock(return_value=b"")
        self.addCleanup(patcher.stop)

    def test_execution_time(self):
        # We want to measure if STT and LLM run in parallel (pipelined) or sequential.

        with patch("my_typeless.worker.STTClient") as MockSTT, \
             patch("my_typeless.worker.LLMClient") as MockLLM, \
             patch("my_typeless.worker.inject_text") as mock_inject:

            stt_instance = MockSTT.return_value
            llm_instance = MockLLM.return_value

            # STT takes 0.1s
            def stt_side_effect(audio, prompt=""):
                time.sleep(0.1)
                return "text"
            stt_instance.transcribe.side_effect = stt_side_effect

            # LLM takes 0.2s
            def llm_side_effect(text, system_prompt="", context=""):
                time.sleep(0.2)
                return "refined"
            llm_instance.refine.side_effect = llm_side_effect

            worker = Worker(self.config)
            worker.start_recording()

            # Push 3 segments
            worker._on_segment(b"seg1")
            worker._on_segment(b"seg2")
            worker._on_segment(b"seg3")

            start_time = time.time()
            worker.stop_recording_and_process()

            # Wait for completion
            # Since we can't join the thread, we poll `mock_inject`
            timeout = 5
            while not mock_inject.called and time.time() - start_time < timeout:
                time.sleep(0.05)

            end_time = time.time()
            duration = end_time - start_time
            print(f"Processing duration: {duration:.4f}s")

            self.assertTrue(mock_inject.called, "inject_text was not called")
            self.assertEqual(stt_instance.transcribe.call_count, 3)
            self.assertEqual(llm_instance.refine.call_count, 3)

            # Expected durations:
            # Sequential: (0.1 + 0.2) * 3 = 0.9s
            # Pipelined: ~0.7s
            self.assertLess(duration, 0.8, "Processing should be pipelined and finish under 0.8s")

if __name__ == "__main__":
    unittest.main()
