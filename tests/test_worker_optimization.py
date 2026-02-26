
import sys
import unittest
from unittest.mock import MagicMock, patch
import queue
import time
import threading

# Mock dependencies before importing my_typeless modules
sys.modules['pyaudio'] = MagicMock()
sys.modules['keyboard'] = MagicMock()
sys.modules['win32api'] = MagicMock()
sys.modules['win32con'] = MagicMock()
sys.modules['win32clipboard'] = MagicMock()
sys.modules['win32gui'] = MagicMock()
# Mock openai if needed, but STTClient/LLMClient mocking below handles it
sys.modules['openai'] = MagicMock()

# Now import the modules under test
# Need to add src to path
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from my_typeless.worker import Worker
from my_typeless.config import AppConfig

class TestWorkerOptimization(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig()
        # Mock STTClient and LLMClient to avoid real API calls and verify instantiation
        self.stt_patcher = patch('my_typeless.worker.STTClient')
        self.llm_patcher = patch('my_typeless.worker.LLMClient')
        self.MockSTTClient = self.stt_patcher.start()
        self.MockLLMClient = self.llm_patcher.start()

        # Setup mocks behavior
        self.mock_stt_instance = self.MockSTTClient.return_value
        self.mock_stt_instance.transcribe.return_value = "Test transcription"

        self.mock_llm_instance = self.MockLLMClient.return_value
        self.mock_llm_instance.refine.return_value = "Test refined text"

        # Mock Recorder to avoid real audio recording logic if needed
        # Worker uses _recorder internally. We can mock it.
        # But Worker instantiates Recorder in __init__. So we patch before Worker init?
        # Actually Worker imports Recorder. We can patch my_typeless.worker.Recorder
        self.recorder_patcher = patch('my_typeless.worker.Recorder')
        self.MockRecorder = self.recorder_patcher.start()
        self.mock_recorder_instance = self.MockRecorder.return_value
        # Mock stop() to return empty bytes to avoid infinite loop or errors
        self.mock_recorder_instance.stop.return_value = b''

        # Mock inject_text and add_history to avoid side effects
        self.inject_patcher = patch('my_typeless.worker.inject_text')
        self.history_patcher = patch('my_typeless.worker.add_history')
        self.mock_inject = self.inject_patcher.start()
        self.mock_history = self.history_patcher.start()

    def tearDown(self):
        self.stt_patcher.stop()
        self.llm_patcher.stop()
        self.recorder_patcher.stop()
        self.inject_patcher.stop()
        self.history_patcher.stop()

    def test_client_reuse(self):
        worker = Worker(self.config)

        # Start recording 1
        worker.start_recording()
        # Simulate some audio segment
        worker._on_segment(b'audio data')
        # Stop recording
        worker.stop_recording_and_process()

        # Wait for processing to finish (worker emits 'state_changed' to 'idle')
        done_event = threading.Event()
        def on_state_changed(state):
            if state == 'idle':
                done_event.set()

        worker.events.on('state_changed', on_state_changed)

        # Wait for done_event
        if not done_event.wait(timeout=2):
            self.fail("Worker processing timed out")

        # Verify instantiation count
        # Should be 1
        self.assertEqual(self.MockSTTClient.call_count, 1)
        self.assertEqual(self.MockLLMClient.call_count, 1)

        # Reset done event
        done_event.clear()

        # Start recording 2
        worker.start_recording()
        worker._on_segment(b'audio data 2')
        worker.stop_recording_and_process()

        if not done_event.wait(timeout=2):
            self.fail("Worker processing 2 timed out")

        # Verify instantiation count again
        # Should still be 1 after optimization
        self.assertEqual(self.MockSTTClient.call_count, 1)
        self.assertEqual(self.MockLLMClient.call_count, 1)

    def test_config_update_resets_clients(self):
        worker = Worker(self.config)

        # Run 1
        worker.start_recording()
        worker.stop_recording_and_process()

        # Wait for idle
        done_event = threading.Event()
        def on_state_changed(state):
            if state == 'idle':
                done_event.set()
        worker.events.on('state_changed', on_state_changed)

        if not done_event.wait(timeout=2):
            self.fail("Worker processing timed out")

        self.assertEqual(self.MockSTTClient.call_count, 1)

        done_event.clear()

        # Update config
        new_config = AppConfig() # creates new instance
        worker.update_config(new_config)

        # Run 2
        worker.start_recording()
        worker.stop_recording_and_process()

        if not done_event.wait(timeout=2):
            self.fail("Worker processing 2 timed out")

        # Should be 2 because config update invalidated cache
        self.assertEqual(self.MockSTTClient.call_count, 2)
        self.assertEqual(self.MockLLMClient.call_count, 2)

if __name__ == '__main__':
    unittest.main()
