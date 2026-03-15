## 2024-03-24 - Fast RMS calculation with math.hypot
**Learning:** When optimizing Python hot loops in the codebase (e.g., audio chunk processing), using the C-optimized `math.hypot(*samples)` function is significantly faster (typically ~2.5x to 7.5x) than using Python generator expressions or `math.dist` for computing the root mean square (RMS) of audio samples.
**Action:** Use `math.hypot(*samples) / math.sqrt(len(samples))` for fast Euclidean distance/RMS calculations on numerical data tuples instead of pure Python loops or generator expressions.
