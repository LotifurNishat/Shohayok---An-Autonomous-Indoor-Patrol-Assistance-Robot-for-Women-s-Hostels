from gpiozero import LineSensor
from time import sleep

# Initialize GPIO 5 as a digital line sensor
# pull_up=False uses the Pi's default pulldown configuration
sensor = LineSensor(5, pull_up=False)

print("Starting LM393 Sensor 1 Test on GPIO 5...")
print("Move the sensor between White and Black surfaces.")
print("Press Ctrl+C to exit.\n")

try:
    while True:
        # sensor.value reads 0 or 1
        raw_val = sensor.value
        state_label = "HIGH (1)" if raw_val == 1 else "LOW (0)"
        print(f"Sensor Raw: {raw_val} -> Pin State: {state_label}")
        sleep(0.3)
except KeyboardInterrupt:
    print("\nTest completed.")
