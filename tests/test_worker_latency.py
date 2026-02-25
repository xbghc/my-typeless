import sys
import time
import threading
import logging
from unittest.mock import MagicMock

logging.basicConfig(level=logging.DEBUG)

# --- 1. Patch platform-specific modules BEFORE imports ---
mock_win32clipboard = MagicMock()
mock_win32con = MagicMock()
mock_keyboard = MagicMock()
mock_pyaudio = MagicMock()
mock_openai = MagicMock()

# Create dummy Exception classes for openai
class AuthError(Exception): pass
mock_openai.AuthenticationError = AuthError
mock_openai.APIConnectionError = Exception
mock_openai.NotFoundError = Exception
mock_openai.BadRequestError = Exception
mock_openai.APITimeoutError = Exception
mock_openai.RateLimitError = Exception
mock_openai.APIStatusError = Exception

sys.modules["win32clipboard"] = mock_win32clipboard
sys.modules["win32con"] = mock_win32con
sys.modules["keyboard"] = mock_keyboard
sys.modules["pyaudio"] = mock_pyaudio
sys.modules["openai"] = mock_openai

# Patch my_typeless modules that use platform libs
sys.modules["my_typeless.text_injector"] = MagicMock()
# We allow recorder to be imported but patch pyaudio inside it?
# No, let's just mock Recorder entirely for simplicity.
sys.modules["my_typeless.recorder"] = MagicMock()

# --- 2. Import Worker ---
from my_typeless.worker import Worker
from my_typeless.config import AppConfig
import my_typeless.worker

# --- 3. Define Mocks for Logic ---

class MockSTTClient:
    def __init__(self, config):
        pass
    def transcribe(self, audio_data, prompt=None):
        time.sleep(0.5)  # Simulate 0.5s STT processing
        return "transcribed text "

class MockLLMClient:
    def __init__(self, config):
        pass
    def refine(self, text, system_prompt=None, context=None):
        time.sleep(0.5)  # Simulate 0.5s LLM processing
        return "refined text "

# Apply logic mocks
my_typeless.worker.STTClient = MockSTTClient
my_typeless.worker.LLMClient = MockLLMClient
my_typeless.worker.inject_text = MagicMock()
my_typeless.worker.add_history = MagicMock()

def run_benchmark():
    print("Setting up benchmark...")
    config = MagicMock(spec=AppConfig)
    config.stt = MagicMock()
    config.llm = MagicMock()
    config.build_stt_prompt.return_value = ""
    config.build_llm_system_prompt.return_value = ""

    # Create worker
    worker = Worker(config)

    # Capture the internal recorder mock
    # Since we mocked the module, Recorder() returned a Mock.
    mock_recorder_instance = worker._recorder
    mock_recorder_instance.stop.return_value = b""

    # Prepare synchronization
    processed_count = 0
    done_event = threading.Event()

    def on_result(text):
        nonlocal processed_count
        processed_count += 1
        # In current implementation, result_ready fires only once at end.
        done_event.set()

    worker.events.on("result_ready", on_result)

    print("Starting worker...")
    start_time = time.time()
    worker.start_recording()

    # Retrieve the callback passed to start()
    # call_args is (args, kwargs). We want kwargs['on_segment']
    # If called positionally, it might be in args.
    # Definition: start(self, on_segment=None)
    # Call in worker: self._recorder.start(on_segment=self._on_segment)
    call_kwargs = mock_recorder_instance.start.call_args[1]
    on_segment = call_kwargs.get('on_segment')

    if not on_segment:
        print("Error: Could not capture on_segment callback")
        return

    # Simulate 3 chunks feeding in quickly
    chunks = [b"chunk1", b"chunk2", b"chunk3"]
    for i, chunk in enumerate(chunks):
        # print(f"  <- Feeding chunk {i+1}")
        on_segment(chunk)
        # Small delay to ensure order in queue, but negligible compared to processing
        time.sleep(0.01)

    # Stop recording (flushes queue)
    worker.stop_recording_and_process()

    # Wait for completion
    if not done_event.wait(timeout=10):
        print("Timeout waiting for processing!")
        print(f"Processed count: {processed_count}")
    else:
        end_time = time.time()
        total_time = end_time - start_time
        print(f"Total time for {len(chunks)} chunks: {total_time:.2f}s")

if __name__ == "__main__":
    run_benchmark()
