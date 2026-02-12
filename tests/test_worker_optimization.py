import sys
from unittest.mock import MagicMock

# Define a mock QObject class
class MockQObject:
    def __init__(self, *args, **kwargs):
        pass

# Mock dependencies before import
sys.modules["pyaudio"] = MagicMock()
sys.modules["PyQt6"] = MagicMock()

mock_qt_core = MagicMock()
mock_qt_core.QObject = MockQObject
mock_qt_core.pyqtSignal = MagicMock()
sys.modules["PyQt6.QtCore"] = mock_qt_core

sys.modules["openai"] = MagicMock()
sys.modules["keyboard"] = MagicMock()
sys.modules["win32api"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["win32gui"] = MagicMock()
sys.modules["win32clipboard"] = MagicMock()

import unittest
# Add src to path so we can import my_typeless
sys.path.insert(0, "src")

from my_typeless.worker import Worker

class TestWorkerOptimization(unittest.TestCase):
    def test_get_tail_text(self):
        # Test case 1: total length < max_len
        parts = ["Hello", " ", "World"]
        self.assertEqual(Worker._get_tail_text(parts, 100), "Hello World")

        # Test case 2: total length > max_len
        parts = ["Prefix", "Keep", "Me"]
        # "KeepMe" len is 6. "PrefixKeepMe" len is 12.
        # If max_len is 6, should return "KeepMe"
        self.assertEqual(Worker._get_tail_text(parts, 6), "KeepMe")

        # Test case 3: cut in middle of a part
        parts = ["A long sentence", " short"]
        # "A long sentence short"
        # max_len = 5 -> "short"
        self.assertEqual(Worker._get_tail_text(parts, 5), "short")
        # max_len = 6 -> " short"
        self.assertEqual(Worker._get_tail_text(parts, 6), " short")
        # max_len = 10 -> "ence short"
        self.assertEqual(Worker._get_tail_text(parts, 10), "ence short")

        # Test case 4: empty parts
        self.assertEqual(Worker._get_tail_text([], 10), "")

        # Test case 5: max_len 0
        self.assertEqual(Worker._get_tail_text(["a", "b"], 0), "")

if __name__ == "__main__":
    unittest.main()
