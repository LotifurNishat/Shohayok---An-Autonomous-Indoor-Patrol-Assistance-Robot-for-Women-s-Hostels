import sys
from time import sleep
from mfrc522 import SimpleMFRC522

# Initialize the RFID reader
try:
    reader = SimpleMFRC522()
except Exception as e:
    print(f"Error initializing SPI/RFID: {e}")
    sys.exit(1)

print("========================================")
print("     MFRC522 RFID Checkpoint Test       ")
print("========================================")
print("Place an RFID tag or card near the reader.")
print("Press Ctrl+C to stop.\n")

try:
    while True:
        # reader.read() blocks until a tag is detected
        print("Waiting for tag...")
        tag_id, text = reader.read()
        
        print(f"-> TAG DETECTED! Unique ID: {tag_id}")
        sleep(1.5)  # Pause to avoid reading the same tag 50 times a second

except KeyboardInterrupt:
    print("\nRFID test stopped.")
finally:
    # Cleanup GPIO resources used by the library
    import RPi.GPIO as GPIO
    GPIO.cleanup()
