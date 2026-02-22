from fastapi import FastAPI
from typing import List
from enum import Enum
from pydantic import BaseModel

import numpy as np
from scipy.signal import find_peaks, butter, filtfilt

fs = 50  # Example: 50Hz (50 samples per second)
 
app = FastAPI()

class Emotions(Enum):
    NEUTRAL = 1
    CALM = 2
    HAPPY = 3
    SAD = 4
    ANGRY = 5
    NERVOUS = 6

class AccelData(BaseModel):
    data: List[float]

accelerations = []
tempo = 70
mood = Emotions.NEUTRAL

def calculate_tempo(data, sampling_rate):
    # 1. Low-pass filter to remove jitter (cutoff at 5Hz)
    nyquist = 0.5 * sampling_rate
    b, a = butter(3, 5 / nyquist, btype='low')
    smoothed_data = filtfilt(b, a, data)

    # 2. Peak detection
    # 'distance' ensures we don't count two peaks within 0.3 seconds of each other
    # 'height' should be adjusted based on your sensor's sensitivity
    peaks, _ = find_peaks(smoothed_data, distance=sampling_rate * 0.3, height=np.mean(smoothed_data))

    # 3. Calculate Step Time (Inter-Step Interval)
    if len(peaks) < 2:
        return 0, 0
    
    intervals = np.diff(peaks) / sampling_rate  # Convert sample distance to seconds
    avg_interval = np.mean(intervals)
    
    # 4. Convert to Steps Per Minute (SPM)
    # Remember: 1 foot sensor captures every OTHER step. Multiply by 2 for total cadence.
    single_foot_spm = 60 / avg_interval
    total_cadence = single_foot_spm * 2
    
    return total_cadence, peaks
 
@app.get("/")
async def root():
  return "hey there"

@app.post("/acc_data")
async def receive_accelerations(payload: AccelData):
    print(f"Received {len(payload.data)} acceleration points.")
    print(payload.data)
    # You can now pass payload.data to your RL model or processing script
    return {"received": len(payload.data)}

@app.get("/tempo_mood")
async def get_tempo_mood():
   cadence, peak_indices = calculate_tempo(accelerations, fs)
   tempo = 2*cadence
   return tempo, mood
