## 2024-05-24 - Fast RMS calculation with math.hypot
**Learning:** When calculating the root mean square (RMS) of audio samples (which are tuples from struct.unpack), `math.hypot(*samples) / math.sqrt(count)` is significantly faster (~2.5x) than calculating the sum of squares with a generator expression (`sum(s * s for s in samples)`) or map.
**Action:** Use `math.hypot(*samples)` for fast Euclidean norm calculations when processing audio frames or any structured byte data.
