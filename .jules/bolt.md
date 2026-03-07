## 2024-03-01 - Optimize audio frame RMS calculation
**Learning:** For computing the root mean square (RMS) of audio chunks, using `math.hypot(*samples) / math.sqrt(count)` is significantly faster (~3.4x) than using a Python generator expression `math.sqrt(sum(s * s for s in samples) / count)`.
**Action:** When calculating RMS over short loops or chunked data where the unpacked item count (e.g. 512 elements) doesn't exceed CPython stack constraints, use C-optimized functions like `math.hypot(*samples)` instead of native Python loops.
