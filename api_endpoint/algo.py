from fastapi import FastAPI
from typing import List
from enum import Enum
from pydantic import BaseModel
import numpy as np
import time

# ============================================
# CONFIG
# ============================================

fs = 5
MAX_INTERVALS = 10

# ============================================
# APP INIT
# ============================================

app = FastAPI()

# ============================================
# ENUMS
# ============================================

class Emotions(Enum):
    NEUTRAL = 1
    CALM = 2
    HAPPY = 3
    SAD = 4
    ANGRY = 5
    NERVOUS = 6

# ============================================
# INPUT MODEL (UNCHANGED)
# ============================================

class AccelData(BaseModel):
    data: List[float]

# ============================================
# GLOBAL STATE
# ============================================

running_avg = 0.0
prev_sample = None
last_cross_sample = None
cross_intervals = []

global_sample_index = 0

current_bpm = 65
current_mood = Emotions.NEUTRAL
last_activity_sample = 0
STILL_THRESHOLD_SECONDS = 2

last_accelerometer_seen = 0.0
last_led_seen = 0.0
DEVICE_TIMEOUT_SECONDS = 15

# ============================================
# ZERO-CROSSING ENGINE
# ============================================

def calculate_tempo(data, sampling_rate):
    global running_avg
    global prev_sample
    global last_cross_sample
    global cross_intervals
    global global_sample_index
    global last_activity_sample

    data = np.array(data)

    if len(data) == 0:
        return 65, []

    alpha = 0.1
    DEAD_ZONE = 1.2
    crossings = []

    for sample in data:
        running_avg = alpha * sample + (1 - alpha) * running_avg
        centered = sample - running_avg
        if prev_sample is not None:
            if prev_sample < -DEAD_ZONE and centered >= DEAD_ZONE:
                if last_cross_sample is not None:
                    interval = (global_sample_index - last_cross_sample) / sampling_rate
                    if interval >= 0.4:
                        cross_intervals.append(interval)
                        if len(cross_intervals) > MAX_INTERVALS:
                            cross_intervals.pop(0)

                last_cross_sample = global_sample_index
                last_activity_sample = global_sample_index
                crossings.append(global_sample_index)

        prev_sample = centered
        global_sample_index += 1

    # 3️⃣ If no intervals → still
    if len(cross_intervals) == 0:
        return 65, crossings
    
    time_since_last_cross = (global_sample_index - last_activity_sample) / sampling_rate

    if time_since_last_cross > STILL_THRESHOLD_SECONDS:
        cross_intervals.clear()
        return 65, crossings

    avg_interval = np.mean(cross_intervals)

    if avg_interval <= 0:
        return 65, crossings

    freq = 1 / avg_interval
    bpm = freq * 60

    bpm = max(40, min(bpm, 180))

    return bpm, crossings

# ============================================
# MOOD CLASSIFIER
# ============================================

def classify_mood(bpm):
    if bpm < 70:
        return Emotions.CALM
    elif bpm < 100:
        return Emotions.NEUTRAL
    elif bpm < 130:
        return Emotions.HAPPY
    elif bpm < 160:
        return Emotions.NERVOUS
    else:
        return Emotions.ANGRY

# ============================================
# ROUTES
# ============================================

@app.get("/")
async def root():
    return {"message": "Cadence engine running"}

@app.post("/acc_data")
async def receive_accelerations(payload: AccelData):
    global current_bpm, current_mood, last_accelerometer_seen

    raw = payload.data
    print("Received batch length:", len(raw))
    print("First 9 values (3 samples):", raw[:9])

    if len(raw) % 3 != 0:
        return {"error": "Data length must be divisible by 3"}

    matrix = np.array(raw).reshape(-1, 3)

    magnitude = np.linalg.norm(matrix, axis=1)

    bpm, _ = calculate_tempo(magnitude, fs)

    print("Calculated BPM:", bpm)

    current_bpm = bpm
    current_mood = classify_mood(bpm)
    last_accelerometer_seen = time.time()

    return {"received": len(matrix)}

@app.get("/tempo_mood")
async def get_tempo_mood():
    now = time.time()

    return {
        "tempo": round(current_bpm, 2),
        "mood": current_mood.name,
        "devices": {
            "accelerometer_connected": (now - last_accelerometer_seen) <= DEVICE_TIMEOUT_SECONDS,
            "led_strip_connected": (now - last_led_seen) <= DEVICE_TIMEOUT_SECONDS,
            "last_accelerometer_seen": last_accelerometer_seen,
            "last_led_seen": last_led_seen,
        },
    }


@app.get("/tempo")
async def get_tempo():
    global last_led_seen

    last_led_seen = time.time()
    return int(round(current_bpm))
