import sys
import time
import threading
import queue
import os
from unittest.mock import MagicMock, patch

# Mock Windows-specific modules and other dependencies
sys.modules["win32clipboard"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["keyboard"] = MagicMock()
sys.modules["pyaudio"] = MagicMock()
sys.modules["openai"] = MagicMock()
# Mock my_typeless.recorder to avoid import errors if pyaudio mock isn't enough
# (recorder.py imports pyaudio, which we mocked, so it should be fine)

# Adjust path to import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from my_typeless.config import AppConfig
from my_typeless.worker import Worker

def run_performance_test():
    with patch('my_typeless.worker.Recorder') as MockRecorder, \
         patch('my_typeless.worker.STTClient') as MockSTTClient, \
         patch('my_typeless.worker.LLMClient') as MockLLMClient, \
         patch('my_typeless.worker.inject_text') as mock_inject, \
         patch('my_typeless.worker.add_history') as mock_history:

        # Configure mocks
        recorder_instance = MockRecorder.return_value
        recorder_instance.stop.return_value = b""

        # Simulate STT taking 0.5s
        stt_instance = MockSTTClient.return_value
        stt_instance.transcribe.side_effect = lambda audio, prompt="": (time.sleep(0.5) or "transcribed text")

        # Simulate LLM taking 0.5s
        llm_instance = MockLLMClient.return_value
        llm_instance.refine.side_effect = lambda text, system_prompt="", context="": (time.sleep(0.5) or "refined text")

        # Initialize Worker
        config = AppConfig()
        worker = Worker(config)

        # Capture state changes to know when done
        done_event = threading.Event()
        def on_state_changed(state):
            if state == "idle":
                done_event.set()
        worker.events.on("state_changed", on_state_changed)

        print("Starting recording...")
        worker.start_recording()

        # Simulate 3 segments arriving "instantly" (queueing up)
        # This tests the throughput of the worker
        print("Queueing 3 segments...")
        worker._on_segment(b"audio1")
        worker._on_segment(b"audio2")
        worker._on_segment(b"audio3")

        # Stop recording, which adds the sentinel to the queue
        worker.stop_recording_and_process()

        print("Waiting for processing to complete...")
        start_time = time.time()

        if not done_event.wait(timeout=10):
            print("TIMEOUT: Worker did not finish in 10s")
            return

        duration = time.time() - start_time
        # Note: start_time is after queuing. The worker might have already started processing seg1.
        # But since we pushed them instantly, likely it's just starting seg1.

        print(f"Processing finished in {duration:.4f}s")
        return duration

if __name__ == "__main__":
    run_performance_test()
