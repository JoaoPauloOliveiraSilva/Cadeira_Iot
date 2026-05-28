import serial
import numpy as np
import requests
import time
import os
import shutil
from datetime import datetime

# ---------- Configuration ----------
SERIAL_PORT = '/dev/ttyACM0'        # Portenta's serial port
BAUD_RATE = 921600                  # Must match Portenta firmware
API_URL = "http://localhost:5000/inference"
SAVE_DIR = os.path.expanduser("~/Desktop/pending_sounds")
TEMP_AUDIO = os.path.expanduser("~/Desktop/temp_event.wav")

# Audio stream settings
SAMPLE_RATE = 16000
CHUNK_DURATION = 0.1                # seconds (100 ms)
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)   # 1600 samples

# Sound activity detection settings
ENERGY_THRESHOLD = 13350              # adjust based on background noise
CONSECUTIVE_TRIGGERS = 5            # number of loud chunks to confirm an event
RECORD_DURATION = 3.0               # seconds to record after detection
RECORD_SAMPLES = int(SAMPLE_RATE * RECORD_DURATION)

os.makedirs(SAVE_DIR, exist_ok=True)

# ---------- Serial connection ----------
print(f"Opening {SERIAL_PORT}...")
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)                       # let Portenta stabilise
ser.reset_input_buffer()

# ---------- Helper functions ----------
def read_chunk():
    """Read exactly CHUNK_SAMPLES * 2 bytes and convert to numpy array."""
    raw = ser.read(CHUNK_SAMPLES * 2)
    if len(raw) < CHUNK_SAMPLES * 2:
        return None
    # Convert raw bytes to 16-bit integers (little-endian)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    return samples

def rms_energy(samples):
    """Return RMS energy of a numpy array."""
    return np.sqrt(np.mean(samples ** 2))

def record_clip(duration_samples):
    """Record a clip of exactly duration_samples samples and save to TEMP_AUDIO."""
    print("  Recording event...")
    recorded = np.zeros(duration_samples, dtype=np.int16)
    collected = 0
    while collected < duration_samples:
        remaining = duration_samples - collected
        raw = ser.read(min(remaining * 2, 4096))   # read up to 4096 bytes
        if not raw:
            continue
        samples = np.frombuffer(raw, dtype=np.int16)
        n = min(len(samples), remaining)
        recorded[collected:collected+n] = samples[:n]
        collected += n
    # Save as WAV (using standard library only)
    save_wav(TEMP_AUDIO, recorded, SAMPLE_RATE)
    print("  Clip saved.")

def save_wav(filename, data, rate):
    """Write a mono 16-bit WAV file (no extra libraries needed)."""
    import struct, wave
    with wave.open(filename, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(data.tobytes())

def classify(file_path):
    """Send audio file to API, return JSON response."""
    with open(file_path, 'rb') as f:
        files = {'audio': f}
        try:
            resp = requests.post(API_URL, files=files, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"  API error: {e}")
            return None

def handle_detection(response):
    """
    Decide what to do based on API response.
    Adapt this to match your API's output format.
    Example formats:
      {"detected": true, "label": "glass_break", "confidence": 0.95}
      {"predictions": [{"class": "breaking", "score": 0.9}]}
    """
    if response is None:
        return
    # Extract label – modify according to your actual API response.
    label = response.get("label", "unknown")
    confidence = response.get("confidence", 0)
    print(f"  Detected: {label} (confidence: {confidence:.2f})")
    
    # Save the clip to send_backend with a descriptive name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(SAVE_DIR, f"{label}_{timestamp}.wav")
    shutil.copy(TEMP_AUDIO, dest)
    print(f"  Saved to {dest}")

# ---------- Main listening loop ----------
print("Listening for sounds... (Ctrl+C to stop)")
trigger_count = 0
listening = True

try:
    while True:
        chunk = read_chunk()
        if chunk is None:
            continue
        energy = rms_energy(chunk)
        
        if energy > ENERGY_THRESHOLD:
            trigger_count += 1
            if trigger_count == CONSECUTIVE_TRIGGERS:
                # Sound event confirmed – record a clip
                record_clip(RECORD_SAMPLES)
                # Send to API and handle result
                result = classify(TEMP_AUDIO)
                handle_detection(result)
                # Reset trigger counter (avoid re-triggering immediately)
                trigger_count = 0
                # Clear any buffered audio from serial during recording
                ser.reset_input_buffer()
        else:
            # If the loudness drops, reset the counter
            trigger_count = 0

except KeyboardInterrupt:
    print("\nStopped.")
finally:
    ser.close()
    if os.path.exists(TEMP_AUDIO):
        os.remove(TEMP_AUDIO)
