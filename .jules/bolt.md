## 2026-03-26 - Audio RMS Calculation Speedup
**Learning:** When calculating the Root Mean Square (RMS) for 1024-sample audio chunks, unpacking samples into `math.hypot(*samples)` is 2.5x to 3x faster than using a Python generator expression `math.sqrt(sum(s * s for s in samples) / count)`. It leverages C-optimized math operations instead of evaluating the hot loop in Python.
**Action:** Use `math.hypot(*samples)` for rapid distance and RMS calculations over short to medium arrays, as long as the array size (e.g. 512-1024 elements) doesn't blow the CPython evaluation stack limit.
