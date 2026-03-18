import math
import struct
import time
import os

SAMPLE_WIDTH = 2
count = 512
data = os.urandom(count * SAMPLE_WIDTH)

def orig_rms(data):
    count = len(data) // SAMPLE_WIDTH
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    sum_sq = sum(s * s for s in samples)
    return math.sqrt(sum_sq / count)

def new_rms(data):
    count = len(data) // SAMPLE_WIDTH
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    return math.hypot(*samples) / math.sqrt(count)

# warm up
orig_rms(data)
new_rms(data)

N = 100000
t0 = time.perf_counter()
for _ in range(N):
    orig_rms(data)
t1 = time.perf_counter()

t2 = time.perf_counter()
for _ in range(N):
    new_rms(data)
t3 = time.perf_counter()

print(f"Original: {t1 - t0:.4f}s")
print(f"New: {t3 - t2:.4f}s")
print(f"Speedup: {(t1 - t0) / (t3 - t2):.2f}x")
