
import sys
import threading
import time
import queue
from unittest.mock import MagicMock, patch

# --- 1. Mock System Modules ---
# We must mock these before importing my_typeless modules because they are Windows-only or rely on hardware.

mock_win32clipboard = MagicMock()
mock_win32con = MagicMock()
mock_keyboard = MagicMock()
mock_pyaudio = MagicMock()

sys.modules["win32clipboard"] = mock_win32clipboard
sys.modules["win32con"] = mock_win32con
sys.modules["keyboard"] = mock_keyboard
sys.modules["pyaudio"] = mock_pyaudio

# Mocking my_typeless.recorder because it imports pyaudio at top level
mock_recorder_module = MagicMock()
sys.modules["my_typeless.recorder"] = mock_recorder_module

# --- 2. Import Application Modules ---
# Now we can import Worker. Note: We need to patch where Worker imports classes.

# We need to mock AppConfig, STTClient, LLMClient, etc.
# Since we are testing Worker logic, we can mock the classes it uses.

from my_typeless.worker import Worker

# --- 3. Verification Script ---

def run_verification():
    print("Starting Worker Pipeline Verification...")

    # Mock Config
    mock_config = MagicMock()
    mock_config.stt = MagicMock()
    mock_config.llm = MagicMock()
    mock_config.build_stt_prompt.return_value = "base_prompt"
    mock_config.build_llm_system_prompt.return_value = "system_prompt"

    # Mock Clients
    mock_stt_instance = MagicMock()
    mock_stt_instance.transcribe.return_value = "Raw Text"

    mock_llm_instance = MagicMock()
    mock_llm_instance.refine.return_value = "Refined Text"

    # Mock Recorder Instance (Worker instantiates it)
    mock_recorder_instance = MagicMock()
    mock_recorder_instance.stop.return_value = b"" # No remaining audio

    # Patch dependencies inside worker.py
    # We need to patch 'my_typeless.worker.STTClient', 'my_typeless.worker.LLMClient', 'my_typeless.worker.Recorder'
    # Also 'my_typeless.worker.inject_text', 'my_typeless.worker.add_history'

    with patch("my_typeless.worker.STTClient", return_value=mock_stt_instance) as MockSTTClient, \
         patch("my_typeless.worker.LLMClient", return_value=mock_llm_instance) as MockLLMClient, \
         patch("my_typeless.worker.Recorder", return_value=mock_recorder_instance), \
         patch("my_typeless.worker.inject_text") as mock_inject, \
         patch("my_typeless.worker.add_history") as mock_history:

        # Instantiate Worker
        worker = Worker(mock_config)

        # Capture events
        events_received = []
        def on_event(event_name, *args):
            print(f"Event received: {event_name} -> {args}")
            events_received.append((event_name, args))

        worker.events.on("state_changed", lambda s: on_event("state_changed", s))
        worker.events.on("result_ready", lambda r: on_event("result_ready", r))
        worker.events.on("error_occurred", lambda m, c: on_event("error_occurred", m, c))

        # --- Test Start Recording ---
        print("\n[Action] Start Recording")
        worker.start_recording()

        # Verify state
        assert "recording" in [e[1][0] for e in events_received if e[0] == "state_changed"]
        print("✓ State changed to recording")

        # --- Test Audio Segment Processing ---
        print("\n[Action] Injecting Audio Segment")
        # Simulate audio segment arrival
        fake_audio = b"\x00\x00" * 100
        worker._on_segment(fake_audio)

        # Wait for processing (threads are running)
        # We can't join threads yet, so we poll or sleep briefly
        time.sleep(0.5)

        # Verify STT was called
        mock_stt_instance.transcribe.assert_called()
        print(f"✓ STT Transcribe called with: {mock_stt_instance.transcribe.call_args}")

        # Verify Text Queue received data
        # Since STT returns "Raw Text", LLM should be called
        time.sleep(0.5)
        mock_llm_instance.refine.assert_called()
        print(f"✓ LLM Refine called with: {mock_llm_instance.refine.call_args}")

        # --- Test Stop Recording ---
        print("\n[Action] Stop Recording")
        worker.stop_recording_and_process()

        # Wait for shutdown (worker threads should finish)
        time.sleep(1.0)

        # Verify final state
        assert "processing" in [e[1][0] for e in events_received if e[0] == "state_changed"]
        assert "idle" == events_received[-1][1][0] # Should return to idle at very end
        print("✓ State returned to idle")

        # Verify Injection
        mock_inject.assert_called_with("Refined Text")
        print("✓ Text injected")

        # Verify History
        mock_history.assert_called()
        print("✓ History added")

        # Verify Result Event
        assert ("result_ready", ("Refined Text",)) in events_received
        print("✓ result_ready event emitted")

        print("\nVerification Passed Successfully!")

if __name__ == "__main__":
    run_verification()
