# TEST 3 (GrovePi): PIR motion sensor on port D7
# NOTE: the PIR needs about 60 seconds after power-up to settle. Early false triggers are normal.

import grovepi
import time

PIR = 7                           # port D7

grovepi.pinMode(PIR, "INPUT")     # this port receives signals from the sensor

last_state = 0                    # previous reading, so we only print changes

print("Warming up... wait about 60 seconds, then wave your hand in front of the sensor")

while True:
    try:
        state = grovepi.digitalRead(PIR)      # 1 = motion detected, 0 = no motion
        if state != last_state:               # report only when it changes
            print("Motion detected!" if state == 1 else "Motion stopped")
            last_state = state
        time.sleep(0.1)                       # 10 checks per second is plenty
    except IOError:
        print("I2C error, retrying")

# Tip: the PIR has two small dials for sensitivity and hold time.
# If "Motion stopped" takes very long to appear, turn the hold-time dial down.
