import sys
from time import sleep
from gpiozero import DistanceSensor

# Initialize HC-SR04
# echo=22, trigger=27
# max_distance=2.0 (measures up to 2 meters)
try:
    sonar = DistanceSensor(echo=22, trigger=27, max_distance=2.0)
except Exception as e:
    print(f"Error initializing sensor: {e}")
    sys.exit(1)

print("========================================")
print("     HC-SR04 Ultrasonic Distance Test   ")
print("========================================")
print("Place an object in front of the sensor. Press Ctrl+C to stop.\n")

try:
    while True:
        # distance property returns meters (0.0 to 2.0)
        distance_cm = sonar.distance * 100

        if distance_cm < 20:
            status = "CRITICAL OBSTACLE (Brake)"
        elif distance_cm < 40:
            status = "Approaching Obstacle"
        else:
            status = "Path Clear"

        print(f"Distance: {distance_cm:6.1f} cm  -->  [{status}]")
        sleep(0.15)

except KeyboardInterrupt:
    print("\nUltrasonic test stopped.")
