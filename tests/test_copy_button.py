import sys
import unittest
import os
from unittest.mock import MagicMock

# Mock dependencies to avoid import errors due to package init
sys.modules["openai"] = MagicMock()
sys.modules["keyboard"] = MagicMock()
sys.modules["pyaudio"] = MagicMock()
# Mock pywin32 modules
sys.modules["win32clipboard"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["win32gui"] = MagicMock()
sys.modules["win32api"] = MagicMock()
# Mock pythoncom just in case
sys.modules["pythoncom"] = MagicMock()


# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

# Import CopyButton AFTER mocks
from my_typeless.settings_window.copy_button import CopyButton

# Create QApplication if it doesn't exist
app = QApplication.instance() or QApplication(sys.argv)

class TestCopyButton(unittest.TestCase):
    def test_copy_button_text(self):
        # Mock clipboard
        clipboard = app.clipboard()
        clipboard.clear()

        btn = CopyButton(lambda: "Text to copy", success_text="Success!")
        btn.setText("Original")

        # Simulate click
        btn.click()

        # Check clipboard
        self.assertEqual(clipboard.text(), "Text to copy")

        # Check visual feedback
        self.assertEqual(btn.text(), "Success!")
        self.assertEqual(btn.toolTip(), "Success!")
        self.assertFalse(btn.isEnabled())

    def test_copy_button_icon(self):
        # Icon only button
        btn = CopyButton(lambda: "Icon text")

        btn.click()

        # Check clipboard
        self.assertEqual(app.clipboard().text(), "Icon text")

        # Check state change
        self.assertFalse(btn.isEnabled())
        self.assertEqual(btn.toolTip(), "Copied!")

if __name__ == '__main__':
    unittest.main()
