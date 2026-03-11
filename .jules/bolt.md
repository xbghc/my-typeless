## 2024-03-24 - Math hypot optimization
**Learning:** When optimizing Python hot loops in the codebase (e.g., audio chunk processing), using the C-optimized `math.hypot(*samples)` function is significantly faster (typically ~3.4x to 7.5x) than using Python generator expressions or `math.dist` for computing the root mean square (RMS) of audio samples.
**Action:** Use `math.hypot(*samples) / math.sqrt(count)` to calculate RMS for small unpacked tuples. Keep in mind CPython evaluation stack limits (512 is safe on modern Python, but significantly larger arrays should use numpy/memoryview).
