from time import sleep
from gpiozero import LED

# Initialize GPIO 17 as an active output pin
test_pin = LED(17)

print("Starting GPIO output test on GPIO 17...")
try:
    for i in range(5):
        print(f"Cycle {i+1}: ON")
        test_pin.on()
        sleep(1)
        print(f"Cycle {i+1}: OFF")
        test_pin.off()
        sleep(1)
    print("Output test completed successfully.")
except KeyboardInterrupt:
    test_pin.off()
    print("\nTest stopped.")
