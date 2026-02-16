
import sys
import time
import threading
import queue
from unittest.mock import MagicMock

# --- Mock modules setup BEFORE importing app modules ---
mock_qt = MagicMock()
class MockQObject:
    def __init__(self, parent=None):
        pass

class MockSignal:
    def __init__(self, *args):
        self._callbacks = []
    def connect(self, cb):
        self._callbacks.append(cb)
    def emit(self, *args):
        for cb in self._callbacks:
            cb(*args)

mock_qt.QObject = MockQObject
mock_qt.pyqtSignal = MockSignal
sys.modules["PyQt6"] = MagicMock()
sys.modules["PyQt6.QtCore"] = mock_qt

sys.modules["pyaudio"] = MagicMock()
sys.modules["keyboard"] = MagicMock()
sys.modules["win32clipboard"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["win32gui"] = MagicMock()
sys.modules["win32api"] = MagicMock()

# Mock internal dependencies
sys.modules["my_typeless.recorder"] = MagicMock()
sys.modules["my_typeless.stt_client"] = MagicMock()
sys.modules["my_typeless.llm_client"] = MagicMock()
sys.modules["my_typeless.text_injector"] = MagicMock()
sys.modules["my_typeless.history"] = MagicMock()

# --- Import Worker ---
# Ensure src is in path
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from my_typeless.worker import Worker
from my_typeless.config import AppConfig

def run_test():
    print("Setting up test...")

    # Setup Config
    config = MagicMock(spec=AppConfig)
    config.stt = MagicMock()
    config.llm = MagicMock()
    config.build_stt_prompt.return_value = "stt_prompt"
    config.build_llm_system_prompt.return_value = "llm_prompt"

    # Setup Recorder Mock
    MockRecorder = sys.modules["my_typeless.recorder"].Recorder
    recorder_instance = MockRecorder.return_value

    captured_on_segment = [None]
    def recorder_start(on_segment=None):
        captured_on_segment[0] = on_segment
    recorder_instance.start.side_effect = recorder_start
    recorder_instance.stop.return_value = b""

    # Setup STTClient
    MockSTTClient = sys.modules["my_typeless.stt_client"].STTClient
    stt_instance = MockSTTClient.return_value

    STT_DELAY = 0.1
    def stt_transcribe(audio, prompt=""):
        time.sleep(STT_DELAY)
        return " raw "
    stt_instance.transcribe.side_effect = stt_transcribe

    # Setup LLMClient
    MockLLMClient = sys.modules["my_typeless.llm_client"].LLMClient
    llm_instance = MockLLMClient.return_value

    LLM_DELAY = 0.1
    def llm_refine(text, system_prompt="", context=""):
        time.sleep(LLM_DELAY)
        return " refined "
    llm_instance.refine.side_effect = llm_refine

    # Setup Worker
    worker = Worker(config)

    finished_event = threading.Event()
    def on_result_ready(text):
        finished_event.set()

    worker.result_ready.connect(on_result_ready)

    print("Starting recording...")
    worker.start_recording()

    time.sleep(0.1)
    if not captured_on_segment[0]:
        print("Error: on_segment not captured")
        return

    # Feed segments
    NUM_SEGMENTS = 5
    print(f"Feeding {NUM_SEGMENTS} segments...")

    # Start timer from when we stop recording?
    # Or include feeding time?
    # If we feed instantly, the queue fills.
    # The processing time starts from when the first item is picked up.
    # But usually we care about "time to result after stopping" OR "total time to result".
    # Let's measure time from Stop to Result.
    # But wait, pipelining helps even during recording.
    # If we measure Total Time (Start Recording -> Result), it includes pauses.
    # We should simulate "speaking" by feeding with delays?
    # Or just feed all at once (simulating a burst of audio processed).
    # If we feed all at once, the queue has 5 items.

    # In Sequential:
    # Pop 1 -> STT -> LLM -> Pop 2 -> ...
    # Time = 5 * (STT + LLM) = 1.0s

    # In Pipelined:
    # Pop 1 -> STT -> Q
    #          Q -> LLM
    # Pop 2 -> STT -> Q
    # ...
    # Time = STT + 4*max(STT, LLM) + LLM = 0.1 + 0.4 + 0.1 = 0.6s

    for i in range(NUM_SEGMENTS):
        captured_on_segment[0](b"audio")

    print("Stopping recording...")
    start_time = time.time()
    worker.stop_recording_and_process()

    if not finished_event.wait(timeout=5.0):
        print("Timeout waiting for result!")
        return

    end_time = time.time()
    # Note: stop_recording_and_process puts _SENTINEL.
    # The worker has to process 5 items + Sentinel.

    # However, if we feed all at once BEFORE stop, the worker might have already processed some.
    # We want to force it to process them.
    # But we want to measure the throughput.
    # If we measure wall clock time for the whole batch?

    # Let's measure time from First Segment fed to Result Ready.
    # But we can't easily capture "first segment fed" in the thread.

    # Let's change strategy:
    # Feed 5 segments. Immediately stop. Measure time.
    # Since we feed in main thread instantly, the worker queue gets 5 items + sentinel almost instantly.
    # The worker starts processing.

    # We should measure time from FEEDING START.

    print(f"Measured time from stop to finish: {end_time - start_time:.4f}s")

    # We need to restart to measure properly because threads are running.
    # Actually, let's just print the time.
    # If the worker was idle before we fed, and we feed 5 items + sentinel.
    # It processes them.
    # If we feed them instantly, and STT is 0.1s.
    # Item 1 starts at T=0.
    # Item 5 starts at T=0.4 (Sequential) or T=0.4 (Pipelined).
    # Wait, STT is the bottleneck in both if STT=LLM=0.1.
    # In Sequential: Item 1 finishes STT at 0.1, LLM at 0.2. Item 2 starts STT at 0.2.
    # In Pipelined: Item 1 finishes STT at 0.1. LLM starts. Item 2 starts STT at 0.1.
    # So Pipelined throughput is doubled.

    pass

if __name__ == "__main__":
    start_all = time.time()
    run_test()
    print(f"Full test run time: {time.time() - start_all:.4f}s")
