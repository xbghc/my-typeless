## 2024-05-24 - Faster RMS calculation using math.hypot
**Learning:** Computing Root Mean Square (RMS) energy over audio buffers is a performance bottleneck in real-time hot loops. Using a Python generator expression `sum(s * s for s in samples)` inside a loop running repeatedly is much slower than utilizing the C-optimized `math.hypot(*samples) / math.sqrt(len)`.
**Action:** Use `math.hypot(*samples) / math.sqrt(count)` for fast RMS calculation. Note: Modern Python safely supports argument unpacking for small buffers (e.g., 512-1024 elements), avoiding stack exhaustion.
