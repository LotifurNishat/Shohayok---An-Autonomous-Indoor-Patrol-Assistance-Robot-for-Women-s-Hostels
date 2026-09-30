from gpiozero import Button
from time import sleep

# Initialize GPIO 27 with an internal pull-down resistor
# When connected to 3.3V -> Pressed (1 / HIGH)
# When floating or connected to GND -> Released (0 / LOW)
test_input = Button(27, pull_up=False)

print("Reading GPIO 27. Touch wire to 3.3V (Pin 1) or GND (Pin 6). Press Ctrl+C to exit.")

try:
    while True:
        if test_input.is_pressed:
            print("GPIO 27: HIGH (3.3V)")
        else:
            print("GPIO 27: LOW (0V)")
        sleep(0.5)
except KeyboardInterrupt:
    print("\nInput test stopped.")
