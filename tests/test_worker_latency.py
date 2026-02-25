import sys
import time
import unittest
from unittest.mock import MagicMock, patch
import queue
import threading

# --- Mocks ---

# Mock pyaudio
mock_pyaudio = MagicMock()
sys.modules["pyaudio"] = mock_pyaudio

# Mock pywin32 modules
mock_win32clipboard = MagicMock()
mock_win32con = MagicMock()
mock_win32gui = MagicMock()
mock_win32api = MagicMock()
sys.modules["win32clipboard"] = mock_win32clipboard
sys.modules["win32con"] = mock_win32con
sys.modules["win32gui"] = mock_win32gui
sys.modules["win32api"] = mock_win32api

# Mock keyboard
mock_keyboard = MagicMock()
sys.modules["keyboard"] = mock_keyboard

# Mock openai
mock_openai = MagicMock()
sys.modules["openai"] = mock_openai

# Mock my_typeless.recorder
mock_recorder_module = MagicMock()
sys.modules["my_typeless.recorder"] = mock_recorder_module

# Mock my_typeless.text_injector
mock_text_injector = MagicMock()
sys.modules["my_typeless.text_injector"] = mock_text_injector

# Mock my_typeless.history
mock_history = MagicMock()
sys.modules["my_typeless.history"] = mock_history

# --- Define Mock Classes ---

class MockRecorder:
    def __init__(self):
        self.on_segment = None
        self._stop_event = threading.Event()

    def start(self, on_segment=None):
        self.on_segment = on_segment
        # Start a thread to simulate audio segments
        threading.Thread(target=self._emit_segments, daemon=True).start()

    def stop(self):
        self._stop_event.set()
        return b""

    def cleanup(self):
        pass

    def _emit_segments(self):
        # Simulate 3 segments
        for i in range(3):
            if self._stop_event.is_set():
                break
            time.sleep(0.1)
            if self.on_segment:
                self.on_segment(f"segment_{i}".encode("utf-8"))

# Assign MockRecorder to the mocked module
mock_recorder_module.Recorder = MockRecorder

# --- Import Worker ---
# Now it's safe to import worker
from my_typeless.worker import Worker
from my_typeless.config import AppConfig

# --- Test Case ---

class TestWorkerLatency(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig()

    @patch("my_typeless.worker.STTClient")
    @patch("my_typeless.worker.LLMClient")
    def test_latency(self, MockLLMClient, MockSTTClient):
        # Setup STT mock
        stt_instance = MockSTTClient.return_value
        def stt_transcribe(audio_data, prompt=None):
            time.sleep(1.0) # Simulate 1s STT
            return f"transcribed_{audio_data.decode('utf-8')}"
        stt_instance.transcribe.side_effect = stt_transcribe

        # Setup LLM mock
        llm_instance = MockLLMClient.return_value
        def llm_refine(text, system_prompt=None, context=None):
            time.sleep(1.0) # Simulate 1s LLM
            return f"refined_{text}"
        llm_instance.refine.side_effect = llm_refine

        worker = Worker(self.config)

        # Capture result
        result_queue = queue.Queue()
        def on_result(text):
            result_queue.put(text)
        worker.events.on("result_ready", on_result)

        print("Starting recording...")
        start_time = time.time()
        worker.start_recording()

        # Wait enough time for all segments to be emitted (3 * 0.1s + some buffer)
        # But we want to wait for the result.
        # The recorder emits 3 segments. The worker processes them.

        # We need to stop recording after some time to trigger final processing?
        # No, the worker processes incrementally. But it only emits 'result_ready' at the end?
        # Let's check worker.py

        # Worker emits 'result_ready' at the end of _incremental_process (after SENTINEL).
        # Sentinel is sent when stop_recording_and_process is called.

        # So we need to call stop_recording_and_process after segments are emitted.
        # But how do we know when segments are emitted?
        # We can wait a bit. 3 segments * 0.1s = 0.3s. Let's wait 0.5s.
        time.sleep(0.5)

        print("Stopping recording...")
        worker.stop_recording_and_process()

        # Wait for result
        try:
            final_text = result_queue.get(timeout=10.0)
            end_time = time.time()
            duration = end_time - start_time
            print(f"Total duration: {duration:.2f}s")
            print(f"Final text: {final_text}")

            # Assertions
            # Expected duration:
            # Sequential: 3 segments * (1s STT + 1s LLM) = 6s. Plus wait time.
            # Pipelined: max(3*1s, 3*1s) + overhead ~ 4s.

            # Since we sleep 0.5s before stopping, the processing starts almost immediately.
            # So 6s is expected for sequential.

            self.assertLess(duration, 5.0, "Should take less than ~5s for pipelined processing")

        except queue.Empty:
            self.fail("Timed out waiting for result")

if __name__ == "__main__":
    unittest.main()
