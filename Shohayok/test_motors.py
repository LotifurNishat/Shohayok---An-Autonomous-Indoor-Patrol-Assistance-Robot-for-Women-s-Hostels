import motors
from time import sleep

print("Testing BOTH motors forward at 80% speed...")
motors.forward(0.8)
sleep(2)
motors.stop()
print("Test complete.")
