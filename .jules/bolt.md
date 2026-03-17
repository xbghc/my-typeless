## 2024-03-17 - Use math.hypot for RMS calculations
**Learning:** Using the C-optimized `math.hypot(*samples)` function is significantly faster (typically ~2.6x or more) than using Python generator expressions like `math.sqrt(sum(s * s for s in samples) / count)` for computing the root mean square (RMS) of audio samples.
**Action:** When calculating RMS for audio chunks or arrays, use `math.hypot(*samples) / math.sqrt(count)` for optimal performance.
