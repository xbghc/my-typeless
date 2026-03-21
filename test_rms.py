import math
import struct
import timeit
import array

def rms_old(data: bytes) -> float:
    SAMPLE_WIDTH = 2
    count = len(data) // SAMPLE_WIDTH
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    sum_sq = sum(s * s for s in samples)
    return math.sqrt(sum_sq / count)

def rms_math_dist(data: bytes) -> float:
    SAMPLE_WIDTH = 2
    count = len(data) // SAMPLE_WIDTH
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    sum_sq = sum(math.dist(samples[i:i + 512], [0]*len(samples[i:i+512]))**2 for i in range(0, count, 512))
    return math.sqrt(sum_sq / count)

def rms_struct_hypot(data: bytes) -> float:
    SAMPLE_WIDTH = 2
    count = len(data) // SAMPLE_WIDTH
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    sum_sq = sum(math.hypot(*samples[i:i + 512]) ** 2 for i in range(0, count, 512))
    return math.sqrt(sum_sq / count)

data = bytes(range(256)) * 8  # 2048 bytes -> 1024 samples

old_time = timeit.timeit("rms_old(data)", setup="from __main__ import rms_old, data", number=10000)
dist_time = timeit.timeit("rms_math_dist(data)", setup="from __main__ import rms_math_dist, data", number=10000)
stru_time = timeit.timeit("rms_struct_hypot(data)", setup="from __main__ import rms_struct_hypot, data", number=10000)

print(f"Old: {old_time:.4f}s")
print(f"Math Dist: {dist_time:.4f}s")
print(f"Struct Hypot: {stru_time:.4f}s")
print(f"Speedup Struct vs Old: {old_time/stru_time:.2f}x")
