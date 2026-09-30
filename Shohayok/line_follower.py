import signal
import sys
from time import sleep, time
from gpiozero import LineSensor, DistanceSensor
from mfrc522 import SimpleMFRC522
import motors

# --- SENSOR GPIO CONFIGURATION ---
left_sensor = LineSensor(6, pull_up=False)
right_sensor = LineSensor(5, pull_up=False)
sonar = DistanceSensor(echo=22, trigger=27, max_distance=2.0)
rfid_reader = SimpleMFRC522()

# --- ZONE MAPPING ---
# Replace with your specific zone designations
ZONES = {
    282334791308: "Zone A (Rooms 101-105)",
    51337757957: "Zone B (Common Area)"
}

# --- SPEED CONFIGURATION ---
RUN_SPEED = 0.38
TURN_SPEED = 0.55
SPIN_SPEED = 0.65

# --- KICKSTART & THRESHOLDS ---
KICK_POWER = 0.90
KICK_DURATION = 0.02
CORNER_SWEEP_TIMEOUT = 0.35
OBSTACLE_THRESHOLD_CM = 15.0

def emergency_stop(sig=None, frame=None):
    print("\n[STOP] Halting motors and cleaning up...")
    motors.stop()
    import RPi.GPIO as GPIO
    GPIO.cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, emergency_stop)

def set_motion_state(new_state, current_state):
    if new_state == current_state:
        return current_state

    if new_state == "FORWARD":
        motors.forward(KICK_POWER)
        sleep(KICK_DURATION)
        motors.forward(RUN_SPEED)
    elif new_state == "SPIN_LEFT":
        motors.spin_left(KICK_POWER)
        sleep(KICK_DURATION)
        motors.spin_left(SPIN_SPEED)
    elif new_state == "SPIN_RIGHT":
        motors.spin_right(KICK_POWER)
        sleep(KICK_DURATION)
        motors.spin_right(SPIN_SPEED)
    elif new_state == "STOP":
        motors.stop()

    return new_state

def main():
    print("========================================")
    print(" NIRAPOD Stage 11: Zone Patrol Checkpoints")
    print("========================================")
    print("Place robot on track. Starting in 3 seconds...")
    sleep(3)

    last_state = "STOP"
    target_state = "STOP"
    last_print_time = 0

    last_turn_dir = None
    lost_line_time = 0
    last_rfid_read_time = 0

    while True:
        # --- PRIORITY 0: ZONE CHECKPOINT DETECTION ---
        # read_no_block() prevents the loop from freezing while waiting for a tag
        tag_id, text = rfid_reader.read_no_block()
        now = time()
        
        # 5-second cooldown prevents the robot from reading the same tag multiple times as it drives over
        if tag_id and (now - last_rfid_read_time > 5.0):
            zone_name = ZONES.get(tag_id, f"Unknown Checkpoint ({tag_id})")
            print(f"\n{'='*40}")
            print(f">>> ARRIVED AT: {zone_name} <<<")
            print(f"{'='*40}\n")
            
            # Halt at checkpoint for 2 seconds
            motors.stop()
            sleep(2)
            
            # Reset navigation memory to prevent erratic corner sweeps upon resuming
            last_rfid_read_time = time()
            lost_line_time = 0
            last_turn_dir = None
            last_state = "STOP" 
            print("Resuming patrol...")

        left_val = left_sensor.value
        right_val = right_sensor.value
        distance_cm = sonar.distance * 100
        now = time()

        if now - last_print_time > 0.15:
            print(f"IR: L={left_val} R={right_val} | Dist: {distance_cm:5.1f}cm | Mode: {last_state}")
            last_print_time = now

        # --- PRIORITY 1: OBSTACLE DETECTION ---
        if distance_cm < OBSTACLE_THRESHOLD_CM:
            target_state = "STOP"
            last_turn_dir = None
            lost_line_time = 0

        # --- PRIORITY 2: LINE FOLLOWING ---
        else:
            if left_val == 0 and right_val == 0:
                if lost_line_time == 0:
                    lost_line_time = now
                if last_turn_dir is not None and (now - lost_line_time) < CORNER_SWEEP_TIMEOUT:
                    target_state = f"SPIN_{last_turn_dir}"
                else:
                    target_state = "FORWARD"
                    last_turn_dir = None
            elif left_val == 1 and right_val == 0:
                target_state = "SPIN_LEFT"
                last_turn_dir = "LEFT"
                lost_line_time = 0
            elif left_val == 0 and right_val == 1:
                target_state = "SPIN_RIGHT"
                last_turn_dir = "RIGHT"
                lost_line_time = 0
            else:
                target_state = "STOP"
                last_turn_dir = None
                lost_line_time = 0

        last_state = set_motion_state(target_state, last_state)
        sleep(0.005)

if __name__ == "__main__":
    main()
