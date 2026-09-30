import signal
import sys
from time import sleep
import motors

# --- SPEED AND TIMING CONFIGURATION ---
FWD_SPEED = 0.40          # Speed for driving straight
SPIN_SPEED = 0.50         # Speed for the pivot
TURN_DURATION = 0.8      # SECONDS TO SPIN - Adjust this to get exactly 90 degrees!

def emergency_stop(sig=None, frame=None):
    print("\n[STOP] Halting motors.")
    motors.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, emergency_stop)

def main():
    print("========================================")
    print("      Open-Loop 90-Degree Turn Test     ")
    print("========================================")
    print("Starting in 3 seconds. Clear the area!")
    sleep(3)

    # 1. Move Forward for 5 seconds
    print("Driving Forward...")
    motors.forward(FWD_SPEED)
    sleep(5.0)

    # Brief stop to kill momentum before turning
    motors.stop()
    sleep(0.5)

    # 2. Spin 90 Degrees
    print(f"Spinning Right for {TURN_DURATION} seconds...")
    motors.spin_right(SPIN_SPEED)
    sleep(TURN_DURATION)

    # Brief stop to kill momentum before driving straight again
    motors.stop()
    sleep(0.5)

    # 3. Move Forward for 5 seconds
    print("Driving Forward...")
    motors.forward(FWD_SPEED)
    sleep(5.0)

    # Done
    print("Test Complete. Stopping.")
    motors.stop()

if __name__ == "__main__":
    main()
