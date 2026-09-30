from gpiozero import Motor
from time import sleep

# Initialize Left and Right channels with direction and PWM speed control
# Motor(forward_pin, backward_pin, enable_pin)
left_motor = Motor(forward=19, backward=26, enable=13)
right_motor = Motor(forward=16, backward=20, enable=12)

print("Starting motor test in 3 seconds. Keep wheels elevated!")
sleep(3)

try:
    print("Testing FORWARD spin at 50% speed...")
    left_motor.forward(1)
    right_motor.forward(1)
    sleep(2)

    print("Stopping...")
    left_motor.stop()
    right_motor.stop()
    sleep(1)

    print("Testing REVERSE spin at 50% speed...")
    left_motor.backward(1)
    right_motor.backward(1)
    sleep(2)

    print("Stopping...")
    left_motor.stop()
    right_motor.stop()
    print("Test finished successfully.")

except KeyboardInterrupt:
    left_motor.stop()
    right_motor.stop()
    print("\nMotor test aborted.")
