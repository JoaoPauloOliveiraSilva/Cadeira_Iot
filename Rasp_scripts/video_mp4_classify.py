import serial
import time
import os
import requests
import subprocess
from datetime import datetime

SERIAL_PORT = '/dev/ttyACM1'        # Nicla Vision USB port
BAUD_RATE = 115200

# ---- This is the correct endpoint ----
API_URL = "http://localhost:5000/inference/video"
# --------------------------------------

CONFIDENCE_THRESHOLD = 0.7          # you can still filter by confidence later

KEPT_FOLDER = os.path.expanduser("~/Desktop/kept_clips")
TEMP_VIDEO = os.path.expanduser("~/Desktop/temp_clip.mp4")

CLIP_DURATION = 3.0
FPS = 5
TOTAL_FRAMES = int(CLIP_DURATION * FPS)

os.makedirs(KEPT_FOLDER, exist_ok=True)

HEADER = b'\xFF\xD8'
FOOTER = b'\xFF\xD9'

def jpegs_to_mp4(jpeg_list, output_path, fps):
    cmd = [
        'ffmpeg', '-y',
        '-f', 'image2pipe',
        '-vcodec', 'mjpeg',
        '-r', str(fps),
        '-i', '-',
        '-vcodec', 'libx264',
        '-pix_fmt', 'yuv420p',
        output_path
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for jpg in jpeg_list:
        proc.stdin.write(jpg)
    proc.stdin.close()
    proc.wait()

def analyze_video(file_path):
    """Send MP4 to the person-detection server, return True if people detected."""
    try:
        with open(file_path, 'rb') as f:
            # The server expects the field 'video'
            files = {'video': (os.path.basename(file_path), f, 'video/mp4')}
            resp = requests.post(API_URL, files=files, timeout=20)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"  Server error: {e}")
        return False

    # The server returns: {"frames_analysed": ..., "detections": [...]}
    detections = data.get('detections', [])
    if detections:
        print(f"  People detected in {len(detections)} frames.")
        return True
    else:
        print("  No people detected.")
        return False

print(f"Opening {SERIAL_PORT}...")
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
time.sleep(3)
ser.reset_input_buffer()

print(f"Recording {CLIP_DURATION}s clips at {FPS} FPS")
print("Press Ctrl+C to stop.")

buffer = b''
jpeg_buffer = []

try:
    while True:
        if ser.in_waiting:
            buffer += ser.read(ser.in_waiting)

        while True:
            s = buffer.find(HEADER)
            if s == -1:
                break
            e = buffer.find(FOOTER, s + 2)
            if e == -1:
                break

            jpg = buffer[s:e+2]
            buffer = buffer[e+2:]
            jpeg_buffer.append(jpg)

            if len(jpeg_buffer) >= TOTAL_FRAMES:
                jpegs_to_mp4(jpeg_buffer, TEMP_VIDEO, FPS)
                jpeg_buffer = []

                if analyze_video(TEMP_VIDEO):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dest = os.path.join(KEPT_FOLDER, f"detected_{timestamp}.mp4")
                    os.rename(TEMP_VIDEO, dest)
                    print(f"  -> KEPT: {dest}")
                else:
                    os.remove(TEMP_VIDEO)

except KeyboardInterrupt:
    print("\nStopped.")
finally:
    ser.close()
    if os.path.exists(TEMP_VIDEO):
        os.remove(TEMP_VIDEO)
