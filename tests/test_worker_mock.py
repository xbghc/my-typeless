import sys
import threading
import time
import queue
from unittest.mock import MagicMock, patch

# === 1. Mock External Dependencies ===
sys.modules["pyaudio"] = MagicMock()
sys.modules["keyboard"] = MagicMock()
sys.modules["win32clipboard"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["openai"] = MagicMock()

# Mock PyQt6
class MockQObject:
    def __init__(self):
        pass

class MockSignal:
    def __init__(self, *args):
        self._callbacks = []

    def connect(self, func):
        self._callbacks.append(func)

    def emit(self, *args):
        for f in self._callbacks:
            try:
                f(*args)
            except Exception as e:
                print(f"Error in signal callback: {e}")

mock_qt = MagicMock()
mock_qt.QObject = MockQObject
mock_qt.pyqtSignal = MockSignal
sys.modules["PyQt6.QtCore"] = mock_qt

# === 2. Import Worker ===
# Now that mocks are in place, we can import
from my_typeless.worker import Worker
from my_typeless.config import AppConfig

# === 3. Test Logic ===
def test_parallel_pipeline():
    print("Setting up test...")
    # Patch Recorder before creating Worker so __init__ uses the mock
    with patch("my_typeless.worker.Recorder") as MockRecorderClass:
        config = AppConfig()
        worker = Worker(config)
        # Ensure the instance created inside Worker is our mock
        worker._recorder = MockRecorderClass.return_value
        # Mock stop to return empty bytes by default
        worker._recorder.stop.return_value = b""

    # Track results
    results = []
    errors = []

    def on_result(text):
        print(f"Result received: {text}")
        results.append(text)

    def on_error(err):
        print(f"Error received: {err}")
        errors.append(err)

    worker.result_ready.connect(on_result)
    worker.error_occurred.connect(on_error)

    # Patch dependencies
    # Note: We already patched Recorder for __init__, but we need to patch STT/LLM/etc.
    # We don't need to patch Recorder again here since we already replaced worker._recorder with a mock.
    with patch("my_typeless.worker.STTClient") as MockSTT, \
         patch("my_typeless.worker.LLMClient") as MockLLM, \
         patch("my_typeless.worker.inject_text") as mock_inject, \
         patch("my_typeless.worker.add_history") as mock_history:

        # Configure Mocks
        stt_instance = MockSTT.return_value
        # STT returns "TRANS(<data>)"
        stt_instance.transcribe.side_effect = lambda data, prompt="": f"TRANS({data.decode()})"

        llm_instance = MockLLM.return_value
        # LLM returns "REF(<text>)"
        llm_instance.refine.side_effect = lambda text, system_prompt="", context="": f"REF({text})"

        # Start Recording
        print("Starting recording...")
        worker.start_recording()

        # Simulate Audio Segments (Producer)
        # We invoke the callback that Recorder would invoke
        print("Simulating audio segments...")
        worker._on_segment(b"Hello")
        time.sleep(0.1)
        worker._on_segment(b"World")

        # Stop Recording (injects sentinel)
        print("Stopping recording...")
        worker.stop_recording_and_process()

        # Wait for threads to finish
        # Since we don't have direct handles to threads (they are local variables in start_recording),
        # we wait for the result signal.

        print("Waiting for processing...")
        max_wait = 5.0
        start_time = time.time()
        while not results and not errors:
            if time.time() - start_time > max_wait:
                break
            time.sleep(0.1)

        if errors:
            print(f"Test Failed with errors: {errors}")
            sys.exit(1)

        if not results:
            print("Test Failed: Timeout waiting for results.")
            sys.exit(1)

        # Verify Output
        # Segment 1: "Hello" -> "TRANS(Hello)" -> "REF(TRANS(Hello))"
        # Segment 2: "World" -> "TRANS(World)" -> "REF(TRANS(World))"
        # Total: "REF(TRANS(Hello))REF(TRANS(World))"

        expected = "REF(TRANS(Hello))REF(TRANS(World))"
        actual = results[0]

        if actual == expected:
            print("SUCCESS: Output matches expectation.")
            print(f"Got: {actual}")
        else:
            print("FAILURE: Output mismatch.")
            print(f"Expected: {expected}")
            print(f"Got:      {actual}")
            sys.exit(1)

        # Verify Injection
        mock_inject.assert_called_with(expected)
        print("Injection verified.")

if __name__ == "__main__":
    try:
        test_parallel_pipeline()
    except Exception as e:
        print(f"Test crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
