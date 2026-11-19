# TEST 2 (GrovePi): Button on port D2

import grovepi
import time

BUTTON = 2                        # port D2

grovepi.pinMode(BUTTON, "INPUT")  # this port receives signals (from the button)

last_state = 0                    # remember the previous state so we only print when it CHANGES

print("Press the button (Ctrl+C to quit)")

while True:                       # loop forever
    try:
        state = grovepi.digitalRead(BUTTON)   # Grove buttons give 1 when pressed, 0 when released
        if state != last_state:               # only act when the state changed since last check
            print("Button pressed" if state == 1 else "Button released")
            last_state = state                # store the new state for the next comparison
        time.sleep(0.05)                      # check 20 times per second; also acts as simple debouncing
    except IOError:
        print("I2C error, retrying")
