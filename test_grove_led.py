# TEST 1 (GrovePi): LED on port D4

import grovepi            # library that talks to the GrovePi board over I2C
import time               # for pauses between actions

LED = 4                   # the number after the "D" on the port label (D4 -> 4)

grovepi.pinMode(LED, "OUTPUT")   # tell the GrovePi that this port will send signals out (to the LED)

for i in range(5):               # repeat the indented block 5 times
    try:                         # try/except because the Pi-to-GrovePi link occasionally hiccups
        grovepi.digitalWrite(LED, 1)   # 1 = HIGH: LED turns on
        time.sleep(0.5)                # stay on for half a second
        grovepi.digitalWrite(LED, 0)   # 0 = LOW: LED turns off
        time.sleep(0.5)                # stay off for half a second
    except IOError:                    # IOError is what the library raises on an I2C glitch
        print("I2C error, retrying")   # just report it and carry on

print("Done: the LED should have blinked 5 times")
