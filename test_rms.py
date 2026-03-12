import math
import struct
import timeit

data = b'\x00\x01' * 1024
SAMPLE_WIDTH = 2
count = len(data) // SAMPLE_WIDTH
samples = struct.unpack(f"<{count}h", data)

def old_rms(samples, count):
    sum_sq = sum(s * s for s in samples)
    return math.sqrt(sum_sq / count)

def new_rms(samples, count):
    return math.hypot(*samples) / math.sqrt(count)

print("Old:", timeit.timeit(lambda: old_rms(samples, count), number=10000))
print("New:", timeit.timeit(lambda: new_rms(samples, count), number=10000))
