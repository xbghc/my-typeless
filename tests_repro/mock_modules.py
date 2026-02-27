
import sys
from unittest.mock import MagicMock

# Mock pyaudio
pyaudio = MagicMock()
sys.modules["pyaudio"] = pyaudio

# Mock pywin32
win32clipboard = MagicMock()
win32con = MagicMock()
win32gui = MagicMock()
win32api = MagicMock()
sys.modules["win32clipboard"] = win32clipboard
sys.modules["win32con"] = win32con
sys.modules["win32gui"] = win32gui
sys.modules["win32api"] = win32api

# Mock keyboard
keyboard = MagicMock()
sys.modules["keyboard"] = keyboard

# Mock openai
openai = MagicMock()
# Mock exception classes as classes, not instances
class APIError(Exception): pass
class AuthenticationError(APIError): pass
class APIConnectionError(APIError): pass
class NotFoundError(APIError): pass
class BadRequestError(APIError): pass
class APITimeoutError(APIError): pass
class RateLimitError(APIError): pass
class APIStatusError(APIError): pass

openai.APIError = APIError
openai.AuthenticationError = AuthenticationError
openai.APIConnectionError = APIConnectionError
openai.NotFoundError = NotFoundError
openai.BadRequestError = BadRequestError
openai.APITimeoutError = APITimeoutError
openai.RateLimitError = RateLimitError
openai.APIStatusError = APIStatusError

sys.modules["openai"] = openai

# Also mock pystray
pystray = MagicMock()
sys.modules["pystray"] = pystray

# Mock webview
webview = MagicMock()
sys.modules["webview"] = webview
