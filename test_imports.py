import sys
from unittest.mock import MagicMock

# Mock system dependencies
sys.modules["pyaudio"] = MagicMock()
sys.modules["win32clipboard"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["keyboard"] = MagicMock()
sys.modules["openai"] = MagicMock()

# Mock internal modules that depend on system deps if needed,
# but hopefully mocking deps is enough.

try:
    from my_typeless.worker import Worker
    print("Worker imported successfully")
except Exception as e:
    print(f"Import failed: {e}")
