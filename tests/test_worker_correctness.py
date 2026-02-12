import sys
import time
import threading
import queue
import unittest
from unittest.mock import MagicMock, patch

# --- Mocking Infrastructure ---

# 1. Mock PyQt6.QtCore
mock_qt_core = MagicMock()
sys.modules['PyQt6'] = MagicMock()
sys.modules['PyQt6.QtCore'] = mock_qt_core

class MockQObject:
    def __init__(self, *args, **kwargs):
        pass

class MockSignal:
    def __init__(self, *args):
        self.callbacks = []
    def connect(self, func):
        self.callbacks.append(func)
    def emit(self, *args):
        for f in self.callbacks:
            try:
                f(*args)
            except Exception as e:
                print(f"Error in signal callback: {e}")

mock_qt_core.QObject = MockQObject
mock_qt_core.pyqtSignal = MockSignal

# 2. Mock other dependencies
sys.modules['pyaudio'] = MagicMock()
sys.modules['win32clipboard'] = MagicMock()
sys.modules['win32con'] = MagicMock()
sys.modules['keyboard'] = MagicMock()
sys.modules['openai'] = MagicMock()

# 3. Mock internal modules
sys.modules['my_typeless.text_injector'] = MagicMock()
# sys.modules['my_typeless.history'] = MagicMock() # We will patch add_history where imported

# --- Import Worker ---
try:
    from my_typeless.worker import Worker
    from my_typeless.config import AppConfig
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

class TestWorkerCorrectness(unittest.TestCase):
    def setUp(self):
        self.stt_patcher = patch('my_typeless.worker.STTClient')
        self.llm_patcher = patch('my_typeless.worker.LLMClient')
        self.recorder_patcher = patch('my_typeless.worker.Recorder')
        self.inject_patcher = patch('my_typeless.worker.inject_text')
        self.history_patcher = patch('my_typeless.worker.add_history')

        self.MockSTT = self.stt_patcher.start()
        self.MockLLM = self.llm_patcher.start()
        self.MockRecorder = self.recorder_patcher.start()
        self.MockInject = self.inject_patcher.start()
        self.MockHistory = self.history_patcher.start()

        # Configure Recorder
        self.recorder_instance = self.MockRecorder.return_value
        self.recorder_instance.stop.return_value = b""

        # Configure STT/LLM behavior
        # We need side_effect to return different values for different calls
        self.stt_instance = self.MockSTT.return_value
        self.llm_instance = self.MockLLM.return_value

    def tearDown(self):
        self.stt_patcher.stop()
        self.llm_patcher.stop()
        self.recorder_patcher.stop()
        self.inject_patcher.stop()
        self.history_patcher.stop()

    def test_pipeline_correctness(self):
        """Verify that segments are processed in order and concatenated correctly."""

        # Setup mock returns
        # STT returns: "Hello", " world"
        self.stt_instance.transcribe.side_effect = ["Hello", " world"]

        # LLM returns: "Hello", " world."
        # Note: In worker, refined_parts.append(refined)
        # LLM call 1: refine("Hello") -> "Hello"
        # LLM call 2: refine(" world") -> " world."
        self.llm_instance.refine.side_effect = ["Hello", " world."]

        worker = Worker(AppConfig())

        finished_event = threading.Event()
        received_result = []

        def on_result(text):
            received_result.append(text)
            finished_event.set()

        worker.result_ready.connect(on_result)

        worker.start_recording()

        # Simulate 2 segments
        worker._on_segment(b"seg1")
        worker._on_segment(b"seg2")

        # Stop and process
        worker.stop_recording_and_process()

        # Wait for completion
        if not finished_event.wait(timeout=5.0):
            self.fail("Timed out waiting for result")

        # Assertions
        self.assertEqual(len(received_result), 1)
        self.assertEqual(received_result[0], "Hello world.")

        # Verify history call
        # Expected raw: "Hello world"
        # Expected refined: "Hello world."
        self.MockHistory.assert_called_once()
        args, kwargs = self.MockHistory.call_args
        self.assertEqual(args[0], "Hello world")
        self.assertEqual(args[1], "Hello world.")

        # Verify injection
        self.MockInject.assert_called_with("Hello world.")

    def test_stt_error_handling(self):
        """Verify that STT error aborts the pipeline gracefully."""
        self.stt_instance.transcribe.side_effect = Exception("STT Failed")

        worker = Worker(AppConfig())

        error_event = threading.Event()
        idle_event = threading.Event()

        def on_error(msg):
            error_event.set()

        def on_state(state):
            if state == "idle":
                idle_event.set()

        worker.error_occurred.connect(on_error)
        worker.state_changed.connect(on_state)

        worker.start_recording()
        worker._on_segment(b"seg1")
        worker.stop_recording_and_process()

        if not error_event.wait(timeout=5.0):
            self.fail("Error not reported")

        if not idle_event.wait(timeout=5.0):
            self.fail("Worker did not return to idle")

        # Verify NO injection occurred
        self.MockInject.assert_not_called()

if __name__ == "__main__":
    unittest.main()
