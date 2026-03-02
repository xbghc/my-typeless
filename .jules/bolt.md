## 2024-05-24 - [Audio Processing Loop Optimization]
**Learning:** In high-frequency audio processing hot loops (like computing RMS across 16-bit PCM chunks), using the C-optimized `math.dist` function to calculate the Euclidean distance is significantly faster (~2x) than using a Python generator expression for sum of squares (`sum(s*s for s in samples)`).
**Action:** Always favor C-optimized standard library math functions (`math.dist`, `math.hypot`, etc.) over manual generator iteration for hot-loop numerical computations on tuple/iterable data.
