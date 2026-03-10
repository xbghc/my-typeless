import math
import struct
import time

def calculate_rms_old(data: bytes) -> float:
    count = len(data) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    sum_sq = sum(s * s for s in samples)
    return math.sqrt(sum_sq / count)

def calculate_rms_new(data: bytes) -> float:
    count = len(data) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    return math.hypot(*samples) / math.sqrt(count)

def calculate_rms_new2(data: bytes) -> float:
    count = len(data) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    return math.dist(samples, (0,) * count) / math.sqrt(count)

data = b'\x01\x00' * 1024
print("Old:", calculate_rms_old(data))
print("New:", calculate_rms_new(data))
print("New2:", calculate_rms_new2(data))

t0 = time.time()
for _ in range(100000):
    calculate_rms_old(data)
t1 = time.time()
print("Old time:", t1 - t0)

t0 = time.time()
for _ in range(100000):
    calculate_rms_new(data)
t1 = time.time()
print("New time:", t1 - t0)

t0 = time.time()
zero_tuple = (0,) * (len(data) // 2)
for _ in range(100000):
    samples = struct.unpack(f"<{len(data) // 2}h", data)
    math.dist(samples, zero_tuple) / math.sqrt(len(data) // 2)
t1 = time.time()
print("New2 time:", t1 - t0)
