import sys
import unittest
from unittest.mock import MagicMock, patch, ANY

# --- Mocking sys.modules BEFORE importing my_typeless modules ---
# We must mock platform-specific modules that might not exist on the test environment (e.g. Linux)
sys.modules["pyaudio"] = MagicMock()
sys.modules["keyboard"] = MagicMock()
sys.modules["win32clipboard"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["win32gui"] = MagicMock()
sys.modules["win32api"] = MagicMock()

# Mock openai to prevent import errors if not installed, and to control exception classes
mock_openai = MagicMock()
mock_openai.OpenAI = MagicMock() # Ensure OpenAI class is available
sys.modules["openai"] = mock_openai

# Define exception classes on the mock so isinstance checks work
class AuthenticationError(Exception): pass
class APIConnectionError(Exception): pass
class NotFoundError(Exception): pass
class BadRequestError(Exception): pass
class APITimeoutError(Exception): pass
class RateLimitError(Exception): pass
class APIStatusError(Exception): pass

mock_openai.AuthenticationError = AuthenticationError
mock_openai.APIConnectionError = APIConnectionError
mock_openai.NotFoundError = NotFoundError
mock_openai.BadRequestError = BadRequestError
mock_openai.APITimeoutError = APITimeoutError
mock_openai.RateLimitError = RateLimitError
mock_openai.APIStatusError = APIStatusError

# Now safe to import
from my_typeless.config import AppConfig, STTConfig, LLMConfig
from my_typeless.worker import Worker

class TestWorker(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig(
            stt=STTConfig(),
            llm=LLMConfig()
        )

        # Mocks for dependencies
        self.mock_recorder = MagicMock()
        self.mock_recorder.stop.return_value = b"remaining_audio"

        self.recorder_factory = MagicMock(return_value=self.mock_recorder)

        self.mock_stt_client = MagicMock()
        # Mock stt transcribe to return a string
        self.mock_stt_client.transcribe.return_value = "transcribed text"

        self.stt_factory = MagicMock(return_value=self.mock_stt_client)

        self.mock_llm_client = MagicMock()
        self.mock_llm_client.refine.return_value = "refined text"

        self.llm_factory = MagicMock(return_value=self.mock_llm_client)

        self.mock_injector = MagicMock()

        # Patch history to prevent DB creation
        self.history_patcher = patch("my_typeless.worker.add_history")
        self.mock_add_history = self.history_patcher.start()

    def tearDown(self):
        self.history_patcher.stop()

    def test_init(self):
        """Test Worker initialization with factories."""
        worker = Worker(
            self.config,
            recorder_factory=self.recorder_factory,
            stt_client_factory=self.stt_factory,
            llm_client_factory=self.llm_factory,
            text_injector=self.mock_injector
        )
        self.recorder_factory.assert_called_once()
        self.assertEqual(worker._text_injector, self.mock_injector)

    def test_recording_flow(self):
        """Test the full recording flow: Start -> Segment -> Stop -> Process -> Inject."""
        worker = Worker(
            self.config,
            recorder_factory=self.recorder_factory,
            stt_client_factory=self.stt_factory,
            llm_client_factory=self.llm_factory,
            text_injector=self.mock_injector
        )

        events = []
        def on_state_changed(state):
            events.append(state)

        result_ready_mock = MagicMock()
        worker.events.on("state_changed", on_state_changed)
        worker.events.on("result_ready", result_ready_mock)

        # 1. Start Recording
        worker.start_recording()
        self.mock_recorder.start.assert_called_once()
        self.assertIn("recording", events)

        # 2. Simulate audio segment via callback
        _, kwargs = self.mock_recorder.start.call_args
        on_segment = kwargs.get("on_segment")
        self.assertIsNotNone(on_segment)
        on_segment(b"audio_chunk")

        # 3. Stop Recording
        worker.stop_recording_and_process()

        # Wait for processing thread to finish (it emits 'idle' at end)
        import time
        start_time = time.time()
        # Wait up to 2 seconds for "idle" state
        while "idle" not in events[-2:] and time.time() - start_time < 2:
            time.sleep(0.05)

        self.assertIn("processing", events)
        self.assertIn("idle", events)

        # We expect 2 transcriptions: one for the segment, one for the remaining audio
        # Note: worker calls stt.transcribe for every item in queue (except sentinel)
        # We put b"audio_chunk" then stop() puts b"remaining_audio"
        self.assertEqual(self.mock_stt_client.transcribe.call_count, 2)

        # We expect 2 calls to refine
        self.assertEqual(self.mock_llm_client.refine.call_count, 2)

        # Result should be accumulation of both refinements
        # refine returns "refined text" each time.
        # total text = "refined text" + "refined text"
        result_ready_mock.assert_called_with("refined textrefined text")

        # Injector should be called with final text
        self.mock_injector.assert_called_with("refined textrefined text")

    def test_openai_error_handling(self):
        """Test that OpenAI errors are caught and emitted as events."""
        worker = Worker(
            self.config,
            recorder_factory=self.recorder_factory,
            stt_client_factory=self.stt_factory,
            llm_client_factory=self.llm_factory,
            text_injector=self.mock_injector
        )

        # Configure STT client to raise AuthenticationError
        self.mock_stt_client.transcribe.side_effect = AuthenticationError("Invalid Key")

        error_events = []
        worker.events.on("error_occurred", lambda msg, fatal: error_events.append((msg, fatal)))

        worker.start_recording()
        # Trigger processing by stopping
        worker.stop_recording_and_process()

        import time
        time.sleep(0.5) # Wait for thread

        self.assertTrue(len(error_events) > 0, "Should have emitted error event")
        self.assertIn("API 密钥无效", error_events[0][0])
        self.assertTrue(error_events[0][1]) # Fatal error

if __name__ == "__main__":
    unittest.main()
