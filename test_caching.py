import sys
from unittest.mock import MagicMock

# Mock necessary dependencies before importing Worker
sys.modules['pyaudio'] = MagicMock()
sys.modules['pywin32'] = MagicMock()
sys.modules['win32clipboard'] = MagicMock()
sys.modules['win32con'] = MagicMock()
sys.modules['win32gui'] = MagicMock()
sys.modules['win32api'] = MagicMock()
sys.modules['keyboard'] = MagicMock()
sys.modules['openai'] = MagicMock()
sys.modules['my_typeless.text_injector'] = MagicMock()
sys.modules['my_typeless.history'] = MagicMock()

from my_typeless.worker import Worker
from my_typeless.config import AppConfig
from my_typeless.stt_client import STTClient
from my_typeless.llm_client import LLMClient
import threading
import queue

def test_client_caching():
    config = AppConfig()
    worker = Worker(config)

    # Run _incremental_process directly with mock queue
    from my_typeless.worker import _SENTINEL
    q1 = queue.Queue()
    q1.put((_SENTINEL, "time1"))

    worker._incremental_process("start1", q1)

    # Store the initially created clients
    stt_client_1 = worker._stt_client
    llm_client_1 = worker._llm_client

    assert isinstance(stt_client_1, STTClient), "STTClient should be created"
    assert isinstance(llm_client_1, LLMClient), "LLMClient should be created"

    # Run a second recording session
    q2 = queue.Queue()
    q2.put((_SENTINEL, "time2"))

    worker._incremental_process("start2", q2)

    # Store clients after second session
    stt_client_2 = worker._stt_client
    llm_client_2 = worker._llm_client

    # Verify that the same instances are used
    assert stt_client_1 is stt_client_2, "STTClient should be cached and reused"
    assert llm_client_1 is llm_client_2, "LLMClient should be cached and reused"

    print("Test passed: Clients are successfully cached and reused across sessions.")

    # Verify cache invalidation
    worker.update_config(config)
    assert worker._stt_client is None, "STTClient cache should be invalidated"
    assert worker._llm_client is None, "LLMClient cache should be invalidated"

    print("Test passed: Cache is successfully invalidated on config update.")

if __name__ == "__main__":
    test_client_caching()
