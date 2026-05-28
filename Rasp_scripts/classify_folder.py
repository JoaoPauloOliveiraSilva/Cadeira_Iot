# -*- coding: utf-8 -*-
import os
import time
import requests
import shutil
from pathlib import Path
from datetime import datetime

# ---------- Configuration ----------
WATCH_FOLDER = os.path.expanduser("~/Desktop/pending_sounds")
KEPT_FOLDER = os.path.expanduser("~/Desktop/kept_sounds")

API_URL = "http://localhost:5000/inference"
CONFIDENCE_THRESHOLD = 0.7

CHECK_INTERVAL = 1.0  # seconds between folder scans

os.makedirs(WATCH_FOLDER, exist_ok=True)
os.makedirs(KEPT_FOLDER, exist_ok=True)

processed_files = set()

def classify_audio(file_path):
    """Send audio to Edge Impulse local server and return (label, confidence)."""
    try:
        with open(file_path, 'rb') as f:
            files = {'audio': f}
            resp = requests.post(API_URL, files=files, timeout=10)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"  API request failed: {e}")
        return None, 0.0

    # --- Correctly parse the new API format ---
    try:
        results = data.get('results', [])
        if not results:
            return None, 0.0
        # Find the label with the highest 'value'
        top = max(results, key=lambda x: x.get('value', 0))
        label = top.get('label')
        confidence = top.get('value', 0.0)
        return label, confidence
    except Exception as e:
        print(f"  Parsing error: {e}")
        return None, 0.0

def handle_new_file(file_path):
    """Process a single new .wav file."""
    filename = os.path.basename(file_path)
    print(f"Processing: {filename}")

    label, confidence = classify_audio(file_path)

    if label is None or confidence < CONFIDENCE_THRESHOLD:
        print(f"  Low confidence ({confidence:.2f}) - deleting.")
        os.remove(file_path)
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name = f"{label}_{confidence:.2f}_{timestamp}.wav"
    dest = os.path.join(KEPT_FOLDER, new_name)
    shutil.move(str(file_path), dest)
    print(f"  -> KEPT as {new_name}")

# ---------- Main watch loop ----------
print(f"Watching folder: {WATCH_FOLDER}")
print(f"Confidence threshold: {CONFIDENCE_THRESHOLD}")
print("Press Ctrl+C to stop.")

try:
    while True:
        for file_path in Path(WATCH_FOLDER).glob("*.wav"):
            if file_path in processed_files:
                continue
            if file_path.stat().st_size == 0:
                continue

            processed_files.add(file_path)
            handle_new_file(file_path)

        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    print("\nStopped.")
