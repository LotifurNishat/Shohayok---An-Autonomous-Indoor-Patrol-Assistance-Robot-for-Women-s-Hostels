from gpiozero import Buzzer
from time import sleep

# Initialize the buzzer on GPIO 17
buzzer = Buzzer(17)

print("Starting Buzzer Test: 3 Beeps...")

try:
    for i in range(3):
        print(f"Beep {i+1}: ON")
        buzzer.on()
        sleep(0.5)
        
        print(f"Beep {i+1}: OFF")
        buzzer.off()
        sleep(0.5)
        
    print("Buzzer test completed successfully.")

except KeyboardInterrupt:
    buzzer.off()
    print("\nTest aborted.")
