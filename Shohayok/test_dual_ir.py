from gpiozero import LineSensor
from time import sleep

# Initialize Left on GPIO 5 and Right on GPIO 6
left_sensor = LineSensor(5, pull_up=False)
right_sensor = LineSensor(6, pull_up=False)

print("Starting Dual LM393 Test...")
print("Line detected = 1 | Floor detected = 0")
print("Move the sensors over the track to verify states.\n")

try:
    while True:
        left_val = left_sensor.value
        right_val = right_sensor.value

        # Determine navigation interpretation
        if left_val == 0 and right_val == 0:
            status = "Centered between lines / Forward"
        elif left_val == 1 and right_val == 0:
            status = "Left on line -> Turn Left"
        elif left_val == 0 and right_val == 1:
            status = "Right on line -> Turn Right"
        else:
            status = "Both on line (Cross / Stop)"

        print(f"LEFT: {left_val} | RIGHT: {right_val}  -->  [{status}]")
        sleep(0.2)

except KeyboardInterrupt:
    print("\nDual sensor test completed.")
