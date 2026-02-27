import sys
import threading
import time
from unittest.mock import MagicMock, patch

# 1. Mock system/3rd party modules BEFORE importing application code
sys.modules["pyaudio"] = MagicMock()
sys.modules["keyboard"] = MagicMock()
sys.modules["win32clipboard"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["win32gui"] = MagicMock()
sys.modules["win32api"] = MagicMock()
# Mock openai to prevent import errors in stt_client/llm_client
sys.modules["openai"] = MagicMock()

# 2. Import application code
# We need to set PYTHONPATH to include src, or add it to sys.path
import os
sys.path.insert(0, os.path.abspath("src"))

from my_typeless.worker import Worker
from my_typeless.config import AppConfig

def run_test():
    print("Setting up test...")

    # We patch the classes as they are imported in worker.py
    # worker.py has: from my_typeless.stt_client import STTClient
    # So we patch my_typeless.worker.STTClient

    with patch("my_typeless.worker.STTClient") as MockSTTClient, \
         patch("my_typeless.worker.LLMClient") as MockLLMClient, \
         patch("my_typeless.worker.Recorder") as MockRecorder, \
         patch("my_typeless.worker.inject_text") as MockInject, \
         patch("my_typeless.worker.add_history") as MockHistory:

        # Setup Recorder mock to return empty bytes on stop so we don't process extra segments
        mock_recorder_instance = MockRecorder.return_value
        mock_recorder_instance.stop.return_value = b""

        config = AppConfig()
        worker = Worker(config)

        # --- Run 1 ---
        print("Starting Run 1...")
        worker.start_recording()
        # The worker starts a thread. We need to give it time to initialize clients.
        # But we also need it to finish.
        worker.stop_recording_and_process()

        # Give enough time for the thread to process the sentinel and exit
        time.sleep(0.5)

        count_after_run1 = MockSTTClient.call_count
        print(f"Run 1 complete. STTClient instantiated {count_after_run1} times.")

        # --- Run 2 ---
        print("Starting Run 2...")
        worker.start_recording()
        worker.stop_recording_and_process()

        time.sleep(0.5)

        count_after_run2 = MockSTTClient.call_count
        print(f"Run 2 complete. STTClient instantiated {count_after_run2} times (Total).")

        # Verification
        # In current code, it instantiates STTClient every time _incremental_process runs.
        # So we expect count_after_run2 == count_after_run1 + 1 (if run 1 instantiates once)
        # Actually it instantiates once per run. So total should be 2.

        if count_after_run2 > count_after_run1:
            print("Current Behavior: Clients are recreated on every recording.")
        else:
            print("Optimized Behavior: Clients are reused.")

        # Check for optimization goal
        if count_after_run1 == 1 and count_after_run2 == 1:
             print("SUCCESS: Optimization verified!")
             sys.exit(0)
        else:
             print("INFO: Clients NOT reused yet (Expected for baseline).")
             # For the purpose of the test script being a pass/fail check for the optimization:
             # If we haven't applied optimization yet, we exit with non-zero to show it "failed" (or just 0 if we are just probing)
             # But I will use this script to verify the FIX later.
             sys.exit(1)

if __name__ == "__main__":
    run_test()
