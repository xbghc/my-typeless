## 2024-05-15 - Optimizing Python Hot Loops
**Learning:** When optimizing Python hot loops in the codebase (e.g., audio chunk processing), using the C-optimized `math.hypot(*samples)` function is significantly faster (typically ~5x) than using Python generator expressions for computing the root mean square (RMS) of audio samples. CPython 3.13 handles argument unpacking of 512+ elements safely.
**Action:** Use `math.hypot(*samples)` for fast vector magnitude/RMS calculations instead of `math.sqrt(sum(s*s for s in samples))` when dealing with hot loops in audio processing.
