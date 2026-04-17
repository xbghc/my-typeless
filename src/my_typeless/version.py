"""Version module.

Source tree always reads as 0.0.0.dev0; CI generates _version.py at build
time to override (see scripts/build.py). _version.py is gitignored so the
source tree stays clean even after running build scripts locally.
"""

try:
    from my_typeless._version import __version__
except ImportError:
    __version__ = "0.0.0.dev0"
