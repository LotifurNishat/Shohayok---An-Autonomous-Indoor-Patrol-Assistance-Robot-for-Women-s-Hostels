from gpiozero import Motor
from time import sleep

# --- MOTOR GPIO CONFIGURATION ---
# Swap these definitions so 'left' controls the physical left motor
LEFT_FWD = 19
LEFT_BACK = 26
LEFT_PWM = 13

RIGHT_FWD = 16
RIGHT_BACK = 20
RIGHT_PWM = 12

# Initialize motor instances
left = Motor(forward=LEFT_FWD, backward=LEFT_BACK, enable=LEFT_PWM)
right = Motor(forward=RIGHT_FWD, backward=RIGHT_BACK, enable=RIGHT_PWM)

# --- TT MOTOR TORQUE FIX (PWM FREQUENCY) ---
LOW_FREQ = 30

left.forward_device.frequency = LOW_FREQ
left.backward_device.frequency = LOW_FREQ
right.forward_device.frequency = LOW_FREQ
right.backward_device.frequency = LOW_FREQ

# Global default speed settings (range: 0.0 to 1.0)
DEFAULT_SPEED = 0.90
PIVOT_SPEED = 0.85


def forward(speed=DEFAULT_SPEED):
    left.forward(speed)
    right.forward(speed)


def backward(speed=DEFAULT_SPEED):
    left.backward(speed)
    right.backward(speed)


def stop():
    left.stop()
    right.stop()


def turn_left(speed=PIVOT_SPEED):
    """Soft turn: Left wheels stop, right wheels drive forward."""
    left.stop()
    right.forward(speed)


def turn_right(speed=PIVOT_SPEED):
    """Soft turn: Right wheels stop, left wheels drive forward."""
    right.stop()
    left.forward(speed)


def spin_left(speed=PIVOT_SPEED):
    """Point turn: Left wheels reverse, right wheels drive forward."""
    left.backward(speed)
    right.forward(speed)


def spin_right(speed=PIVOT_SPEED):
    """Point turn: Left wheels forward, right wheels reverse."""
    left.forward(speed)
    right.backward(speed)


def set_speeds(left_speed, right_speed):
    """
    Arbitrary differential speed control.
    Accepts values between -1.0 (full reverse) and 1.0 (full forward).
    """
    if left_speed > 0:
        left.forward(min(left_speed, 1.0))
    elif left_speed < 0:
        left.backward(min(abs(left_speed), 1.0))
    else:
        left.stop()

    if right_speed > 0:
        right.forward(min(right_speed, 1.0))
    elif right_speed < 0:
        right.backward(min(abs(right_speed), 1.0))
    else:
        right.stop()


# Standalone diagnostic test
if __name__ == "__main__":
    print("Testing 'motors.py' routines in 2 seconds. Keep wheels elevated!")
    sleep(2)
    try:
        print("1. Forward (90%)")
        forward(0.9)
        sleep(5)

        print("2. Reverse (90%)")
        backward(0.9)
        sleep(5)

        print("3. Spin Left (Counter-clockwise)")
        spin_left(0.85)
        sleep(5)

        print("4. Spin Right (Clockwise)")
        spin_right(0.85)
        sleep(5)

        print("5. Stop")
        stop()
        print("Motor verification routine complete.")
    except KeyboardInterrupt:
        stop()
        print("\nTest aborted.")
