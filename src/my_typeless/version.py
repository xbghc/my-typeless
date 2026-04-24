"""Version module.

Source tree always reads as 0.0.0.dev0; CI generates _version.py at build
time to override (see scripts/build.py). _version.py is gitignored so the
source tree stays clean even after running build scripts locally.
"""

__version__ = "0.0.0.dev0"

try:
    from my_typeless._version import __version__ as _build_version
except ImportError:
    pass
else:
    __version__ = _build_version
