import cv2
import sys
import os
import time
import numpy as np
from picamera2 import Picamera2

# --- CONFIGURATION ---
PROTOTXT_PATH = "MobileNetSSD_deploy.prototxt"
MODEL_PATH = "MobileNetSSD_deploy.caffemodel"
PERSON_CLASS_ID = 15
CONFIDENCE_THRESHOLD = 0.55

if not os.path.exists(PROTOTXT_PATH) or not os.path.exists(MODEL_PATH):
    print("[ERROR] Model files missing. Please run the wget commands to download them.")
    sys.exit(1)

print("[INFO] Loading MobileNet-SSD Deep Learning Network...")
net = cv2.dnn.readNetFromCaffe(PROTOTXT_PATH, MODEL_PATH)

print("[INFO] Initializing Pi 5 Camera Stack (Picamera2)...")
try:
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": (640, 480)})
    picam2.configure(config)
    picam2.start()
except Exception as e:
    print(f"[ERROR] Failed to start camera: {e}")
    sys.exit(1)

print("========================================")
print("  Picamera2 Human Detection Engine Test ")
print("========================================")
print("Step in front of the camera. Press Ctrl+C to stop.\n")

last_print_time = 0

try:
    while True:
        # Capture frame natively via Picamera2
        frame = picam2.capture_array()

        # Drop 4th alpha channel if present and force contiguous memory for OpenCV
        if frame.shape[2] == 4:
            frame = frame[:, :, :3]
        frame = np.ascontiguousarray(frame)

        (h, w) = frame.shape[:2]

        # Convert frame to 300x300 Blob for MobileNet-SSD
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
        net.setInput(blob)
        detections = net.forward()

        person_found = False
        best_confidence = 0

        # Parse detections
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            class_id = int(detections[0, 0, i, 1])

            # Check if the detected object is a person and meets the confidence threshold
            if class_id == PERSON_CLASS_ID and confidence > CONFIDENCE_THRESHOLD:
                person_found = True
                best_confidence = confidence
                break

        # Throttled terminal output (~5Hz)
        now = time.time()
        if now - last_print_time > 0.2:
            if person_found:
                print(f">>> HUMAN DETECTED | Confidence: {best_confidence * 100:.1f}%")
            else:
                print("Scanning...")
            last_print_time = now

        # Short sleep to prevent maxing out the CPU
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nCamera test stopped.")
finally:
    picam2.stop()
