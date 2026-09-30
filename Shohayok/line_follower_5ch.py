import signal
import sys
from time import sleep, time
from gpiozero import LineSensor
import motors

# --- SENSOR GPIO CONFIGURATION ---
ir1 = LineSensor(5, pull_up=False)   # Far Left
ir2 = LineSensor(6, pull_up=False)   # Mid Left
ir3 = LineSensor(23, pull_up=False)  # Center
ir4 = LineSensor(24, pull_up=False)  # Mid Right
ir5 = LineSensor(4, pull_up=False)   # Far Right

# --- SPEED CONFIGURATION ---
RUN_SPEED = 0.38          
TURN_SPEED = 0.45         
SPIN_SPEED = 0.50         # Updated to match your test speed

KICK_POWER = 0.65         
KICK_DURATION = 0.01      
CORNER_SWEEP_TIMEOUT = 0.15

def emergency_stop(sig=None, frame=None):
    print("\n[STOP] Halting motors...")
    motors.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, emergency_stop)

def read_sensors():
    """Reads and inverts sensors (0 = White, 1 = Black line)"""
    return [
        int(ir1.value == 0),
        int(ir2.value == 0),
        int(ir3.value == 0),
        int(ir4.value == 0),
        int(ir5.value == 0)
    ]

def execute_90_degree_turn(direction):
    """
    Halts the main loop to execute a perfect 90-degree pivot.
    Uses separate timings to account for motor asymmetry and a wider sensor catch.
    """
    print(f"\n>>> EXECUTING 90-DEGREE {direction} TURN <<<")
    motors.stop()
    sleep(0.05) # Brief pause to kill forward momentum
    
    if direction == "RIGHT":
        # Right motors are spinning faster/further. 
        # Reduced blind duration so it doesn't overshoot before looking.
        blind_duration = 0.25  
        motors.spin_right(SPIN_SPEED)
        sleep(blind_duration)
        
        timeout = time() + 0.8 
        # Widen the catch: Stop if Center OR Mid-Left OR Mid-Right sees the line
        while True:
            s = read_sensors()
            if s[1] == 1 or s[2] == 1 or s[3] == 1 or time() > timeout:
                break
            sleep(0.01)
            
    elif direction == "LEFT":
        # Left turn was working fine, keep the original timing
        blind_duration = 0.40  
        motors.spin_left(SPIN_SPEED)
        sleep(blind_duration)
        
        timeout = time() + 0.8
        # Widen the catch: Stop if Center OR Mid-Left OR Mid-Right sees the line
        while True:
            s = read_sensors()
            if s[1] == 1 or s[2] == 1 or s[3] == 1 or time() > timeout:
                break
            sleep(0.01)
            
    motors.stop()
    print("<<< Turn complete, returning to line following.")
    sleep(0.05) # Brief pause to stabilize before driving forward

def set_motion_state(new_state, current_state):
    """Handles standard line-following states (Forward/Soft Turns)"""
    if new_state == current_state:
        return current_state

    if new_state == "FORWARD":
        motors.forward(KICK_POWER)
        sleep(KICK_DURATION)
        motors.forward(RUN_SPEED)
        
    elif new_state == "TURN_LEFT":
        motors.turn_left(KICK_POWER)
        sleep(KICK_DURATION)
        motors.turn_left(TURN_SPEED)
        
    elif new_state == "TURN_RIGHT":
        motors.turn_right(KICK_POWER)
        sleep(KICK_DURATION)
        motors.turn_right(TURN_SPEED)

    elif new_state == "STOP":
        motors.stop()

    return new_state

def main():
    print("========================================")
    print("    NIRAPOD 5-Channel Line Follower      ")
    print("========================================")
    sleep(3)

    last_state = "STOP"
    target_state = "STOP"
    last_print_time = 0
    lost_line_time = 0
    last_turn_dir = None

    while True:
        now = time()
        s = read_sensors()

        if now - last_print_time > 0.1:
            print(f"IR Array: {s} | Mode: {last_state}")
            last_print_time = now

        # --- NAVIGATION LOGIC ---
        
        # 1. T-Intersection (Stop)
        if sum(s) >= 4:
            target_state = "STOP"

        # 2. Sharp Left (Trigger Blocking Turn)
        elif s[0] == 1:
            execute_90_degree_turn("LEFT")
            target_state = "FORWARD" # Force forward immediately after turn
            last_state = "STOP"      # Reset state to trigger kickstart

        # 3. Sharp Right (Trigger Blocking Turn)
        elif s[4] == 1:
            execute_90_degree_turn("RIGHT")
            target_state = "FORWARD"
            last_state = "STOP"

        # 4. Forward
        elif s[2] == 1:
            target_state = "FORWARD"
            last_turn_dir = None
            lost_line_time = 0

        # 5. Soft Left Drift
        elif s[1] == 1:
            target_state = "TURN_LEFT"
            last_turn_dir = "LEFT"
            lost_line_time = 0

        # 6. Soft Right Drift
        elif s[3] == 1:
            target_state = "TURN_RIGHT"
            last_turn_dir = "RIGHT"
            lost_line_time = 0

        # 7. Line Lost Recovery
        elif sum(s) == 0:
            if lost_line_time == 0:
                lost_line_time = now
            
            if last_turn_dir is not None and (now - lost_line_time) < CORNER_SWEEP_TIMEOUT:
                # Execute a tiny sweep to find the line
                if last_turn_dir == "LEFT":
                    motors.spin_left(SPIN_SPEED)
                else:
                    motors.spin_right(SPIN_SPEED)
            else:
                target_state = "FORWARD"

        # Apply state for normal driving (ignores blocking turns)
        if s[0] == 0 and s[4] == 0: 
            last_state = set_motion_state(target_state, last_state)
            
        sleep(0.005)

if __name__ == "__main__":
    main()
