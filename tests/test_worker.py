import sys
import unittest
import time
from unittest.mock import MagicMock, patch
from pathlib import Path

# --- MOCKING DEPENDENCIES BEFORE IMPORT ---
# Because we are on Linux without GUI/Audio libs, we must mock these.

# Mock PyQt6
mock_qt = MagicMock()
sys.modules["PyQt6"] = mock_qt
sys.modules["PyQt6.QtCore"] = mock_qt.QtCore
sys.modules["PyQt6.QtWidgets"] = mock_qt.QtWidgets
sys.modules["PyQt6.QtNetwork"] = mock_qt.QtNetwork

# Mock QObject and pyqtSignal
class MockQObject:
    def __init__(self, *args, **kwargs):
        pass

class BoundSignal:
    def __init__(self):
        self.callbacks = []
    def connect(self, callback):
        self.callbacks.append(callback)
    def emit(self, *args):
        for cb in self.callbacks:
            cb(*args)

class MockPyqtSignal:
    def __init__(self, *args):
        pass
    def __get__(self, instance, owner):
        if instance is None:
            return self
        if not hasattr(instance, "_signals"):
            instance._signals = {}
        if self not in instance._signals:
            instance._signals[self] = BoundSignal()
        return instance._signals[self]

mock_qt.QtCore.QObject = MockQObject
mock_qt.QtCore.pyqtSignal = MockPyqtSignal

# Mock pyaudio
sys.modules["pyaudio"] = MagicMock()

# Mock keyboard
sys.modules["keyboard"] = MagicMock()

# Mock win32clipboard and win32con
sys.modules["win32clipboard"] = MagicMock()
sys.modules["win32con"] = MagicMock()

# --- NOW IMPORT WORKER ---
# We need to make sure 'src' is in path
sys.path.append(str(Path(__file__).parent.parent / "src"))

# Now we can safely import modules that use these deps
from my_typeless.worker import Worker
from my_typeless.config import AppConfig

class TestWorker(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig()
        # Ensure we don't actually write files or call APIs
        self.config.save = MagicMock()

    @patch("my_typeless.worker.Recorder")
    @patch("my_typeless.worker.STTClient")
    @patch("my_typeless.worker.LLMClient")
    @patch("my_typeless.worker.inject_text")
    @patch("my_typeless.worker.add_history")
    def test_pipeline_flow(self, mock_add_history, mock_inject, mock_llm_cls, mock_stt_cls, mock_recorder_cls):
        """Test the parallel STT -> LLM pipeline."""

        # Setup mocks
        mock_recorder = mock_recorder_cls.return_value
        mock_recorder.stop.return_value = b""  # Ensure no remaining audio
        mock_stt = mock_stt_cls.return_value
        mock_llm = mock_llm_cls.return_value

        # Configure STT to return different text for different calls
        mock_stt.transcribe.side_effect = ["Hello", " world"]

        # Configure LLM to refine text
        def refine_side_effect(text, system_prompt, context):
            return text.upper()
        mock_llm.refine.side_effect = refine_side_effect

        worker = Worker(self.config)

        # Verify signals
        state_spy = MagicMock()
        result_spy = MagicMock()
        worker.state_changed.connect(state_spy)
        worker.result_ready.connect(result_spy)

        # 1. Start Recording
        worker.start_recording()
        # Verify signal
        state_spy.assert_called_with("recording")

        # 2. Simulate audio segments arriving
        # Access the internal on_segment callback passed to recorder.start
        # Note: start_recording creates a new Recorder instance or uses the one created in __init__
        # In Worker.__init__, self._recorder = Recorder().
        # So mock_recorder_cls() is called there.
        # Then start_recording calls self._recorder.start()

        self.assertTrue(mock_recorder.start.called)
        on_segment = mock_recorder.start.call_args[1]['on_segment']

        on_segment(b"segment1")
        time.sleep(0.1) # Give thread time to pick it up
        on_segment(b"segment2")

        # 3. Stop Recording
        worker.stop_recording_and_process()

        # Wait for processing (max 2 seconds)
        for _ in range(20):
            if mock_inject.called:
                break
            time.sleep(0.1)

        # Verify interactions
        self.assertEqual(mock_stt.transcribe.call_count, 2)
        self.assertEqual(mock_llm.refine.call_count, 2)

        # Verify injection
        # "Hello" -> "HELLO", " world" -> " WORLD"
        # Injected: "HELLO WORLD"
        mock_inject.assert_called_with("HELLO WORLD")

        # Verify history
        mock_add_history.assert_called()
        args = mock_add_history.call_args
        self.assertEqual(args[0][0], "Hello world") # raw
        self.assertEqual(args[0][1], "HELLO WORLD") # refined

        # Verify signal
        result_spy.assert_called_with("HELLO WORLD")

        # Check idle state
        # state_spy calls: recording, processing, idle
        # We can check if 'idle' was called last
        self.assertEqual(state_spy.call_args_list[-1][0][0], "idle")

    @patch("my_typeless.worker.Recorder")
    @patch("my_typeless.worker.STTClient")
    @patch("my_typeless.worker.LLMClient")
    @patch("my_typeless.worker.inject_text")
    def test_stt_error_handling(self, mock_inject, mock_llm_cls, mock_stt_cls, mock_recorder_cls):
        """Test error in STT propagates."""
        mock_stt = mock_stt_cls.return_value
        mock_stt.transcribe.side_effect = Exception("STT Failed")

        worker = Worker(self.config)
        error_spy = MagicMock()
        worker.error_occurred.connect(error_spy)

        worker.start_recording()

        # Inject audio
        on_segment = mock_recorder_cls.return_value.start.call_args[1]['on_segment']
        on_segment(b"data")

        worker.stop_recording_and_process()

        # Wait for error
        for _ in range(20):
            if error_spy.called:
                break
            time.sleep(0.1)

        self.assertTrue(error_spy.called)
        self.assertIn("STT Error", error_spy.call_args[0][0])

        # Verify inject NOT called
        mock_inject.assert_not_called()

if __name__ == "__main__":
    unittest.main()
