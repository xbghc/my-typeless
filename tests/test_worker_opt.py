
import sys
import unittest
from unittest.mock import MagicMock, patch
import time
import threading
import queue

# --- MOCKING START ---
# Mock modules that are not available in the test environment or are hard to test
# These must be mocked BEFORE importing the target module

mock_qt = MagicMock()
class MockQObject:
    def __init__(self, *args, **kwargs):
        pass

mock_qt.QtCore.QObject = MockQObject
mock_qt.QtCore.pyqtSignal = MagicMock(return_value=MagicMock())

sys.modules["PyQt6"] = mock_qt
sys.modules["PyQt6.QtCore"] = mock_qt.QtCore
sys.modules["PyQt6.QtNetwork"] = MagicMock()
sys.modules["PyQt6.QtWidgets"] = MagicMock()

sys.modules["pyaudio"] = MagicMock()
sys.modules["keyboard"] = MagicMock()
sys.modules["win32clipboard"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["openai"] = MagicMock()

# --- MOCKING END ---

# Now we can import the worker
from my_typeless.worker import Worker
from my_typeless.config import AppConfig

class TestWorkerOptimization(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig()

        # Patch dependencies inside Worker
        self.patcher_recorder = patch("my_typeless.worker.Recorder")
        self.MockRecorder = self.patcher_recorder.start()
        # Ensure stop() returns empty bytes so no extra segment is added
        self.MockRecorder.return_value.stop.return_value = b""

        self.patcher_stt = patch("my_typeless.worker.STTClient")
        self.MockSTTClient = self.patcher_stt.start()

        self.patcher_llm = patch("my_typeless.worker.LLMClient")
        self.MockLLMClient = self.patcher_llm.start()

        self.patcher_inject = patch("my_typeless.worker.inject_text")
        self.mock_inject = self.patcher_inject.start()

        self.patcher_history = patch("my_typeless.worker.add_history")
        self.mock_history = self.patcher_history.start()

        self.worker = Worker(self.config)

    def tearDown(self):
        self.patcher_recorder.stop()
        self.patcher_stt.stop()
        self.patcher_llm.stop()
        self.patcher_inject.stop()
        self.patcher_history.stop()
        self.worker.cleanup()

    def test_pipeline_parallelism(self):
        """Verify that STT and LLM tasks run in parallel."""

        # Setup simulated delays
        stt_delay = 0.5
        llm_delay = 0.5

        # Mock STT transcribe
        def mock_transcribe(audio, prompt=None):
            time.sleep(stt_delay)
            return "transcribed"
        self.MockSTTClient.return_value.transcribe.side_effect = mock_transcribe

        # Mock LLM refine
        def mock_refine(text, system_prompt=None, context=None):
            time.sleep(llm_delay)
            return "refined"
        self.MockLLMClient.return_value.refine.side_effect = mock_refine

        # Start recording
        self.worker.start_recording()

        # Simulate 2 audio segments coming in
        # Segment 1
        self.worker._on_segment(b"audio1")
        # Segment 2
        self.worker._on_segment(b"audio2")

        # Stop recording
        start_time = time.time()
        self.worker.stop_recording_and_process()

        # Wait for processing to finish
        # In the original implementation, this would take:
        # Segment 1: 0.5 (STT) + 0.5 (LLM) = 1.0s
        # Segment 2: 0.5 (STT) + 0.5 (LLM) = 1.0s
        # Total = 2.0s

        # With optimization:
        # T=0: STT1 start
        # T=0.5: STT1 done, LLM1 start, STT2 start
        # T=1.0: STT2 done, LLM1 done, LLM2 start
        # T=1.5: LLM2 done
        # Total approx 1.5s

        # Wait for result_ready signal or check manually
        # Since we can't easily connect signals in this mocked env without a loop,
        # we can wait for the threads to join if we had access to them,
        # or we can wait for inject_text to be called.

        # Busy wait for inject_text
        timeout = 3.0
        while timeout > 0:
            if self.mock_inject.called:
                break
            time.sleep(0.1)
            timeout -= 0.1

        end_time = time.time()
        duration = end_time - start_time

        print(f"Total processing time: {duration:.2f}s")

        # Verify result was injected
        self.mock_inject.assert_called_once()
        args = self.mock_inject.call_args[0]
        self.assertEqual(args[0], "refinedrefined") # Two segments joined

        # This test will FAIL if the optimization is not implemented yet
        # because the original code runs sequentially and might take longer?
        # Actually, the original code runs sequentially in ONE thread.
        # The optimized code runs in TWO threads.
        # With 2 segments:
        # Sequential: STT1(0.5) -> LLM1(0.5) -> STT2(0.5) -> LLM2(0.5) = 2.0s
        # Parallel: STT1(0.5) -> (LLM1(0.5) || STT2(0.5)) -> LLM2(0.5) = 1.5s

        # So we assert duration < 1.8s to prove parallelism
        self.assertLess(duration, 1.8, "Processing took too long, parallelism not working")

if __name__ == "__main__":
    unittest.main()
