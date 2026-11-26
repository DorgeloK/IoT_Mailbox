#!/usr/bin/env python3
"""Mailbox sensors: PIR + light sensor + LED patterns + reset button (no network yet)
Wiring (GrovePi):  PIR on D7 | button on D2 | LED on D4 | Si1145 sunlight sensor on an I2C port

LED patterns:
  slow blink   = starting up (PIR warming up, measuring the empty-box light level)
  solid        = idle, everything fine
  fast blink   = motion detected
  double blink = error (a sensor cannot be read)

Button: press it with the box EMPTY. It clears the "mail" state and re-measures the empty-box light level.
Run on the Pi:     python3 mailbox_sensors.py
Test on a laptop:  MAILBOX_SIMULATE=1 python3 mailbox_sensors.py     (fake sensors, no Pi needed)"""

import os
import time
import random

PIR_PORT = 7 # D7
BUTTON_PORT = 2 # D2
LED_PORT = 4 # D4
LIGHT_ADDR = 0x60 # I2C address

SIMULATE = os.environ.get("MAILBOX_SIMULATE", "") == "1"

WARMUP_S = 3 if SIMULATE else 60 # PI needs about 60 s after power-on to settle
MOTION_CONFIRM_S = 1.0 # PIR must stay HIGH this long to count as motion (ignores tiny twitches)
FAST_BLINK_S = 5.0 # how long the LED fast-blinks after motion
SETTLE_S = 5.0 # after motion stops, wait this long before checking for mail
MAIL_DROP = 10 # mail = infrared reading at least this far BELOW the empty-box baseline
MAIL_CLEAR = 5 # "empty again" once the drop shrinks to this or less (stops flicker)
SAMPLES = 10 # light readings averaged per check (one reading is too noisy)
ERROR_AFTER = 5 # this many failed loops in a row = show the error pattern
LOOP_S = 0.1 # main loop runs 10 times per second

START = time.time()


def log(msg):
    # print a message with the seconds since the program started
    print("[%6.1fs] %s" % (time.time() - START, msg), flush=True)


class RealHardware(object):
    """The real GrovePi and the Si1145 light sensor."""

    def __init__(self):
        import grovepi # imported here so a laptop can still run the simulation
        import smbus
        self.grovepi = grovepi
        self.bus = smbus.SMBus(1) # I2C bus 1
        grovepi.pinMode(PIR_PORT, "INPUT")
        grovepi.pinMode(BUTTON_PORT, "INPUT")
        grovepi.pinMode(LED_PORT, "OUTPUT")
        self.light_ready = False # the light sensor is set up on first use (and again after an error)

    def _setup_light(self):
        b = self.bus
        part = b.read_byte_data(LIGHT_ADDR, 0x00) # chip ID, should be 0x45
        if part not in (0x45, 0x46, 0x47):
            raise IOError("unexpected light sensor ID %s" % hex(part))
        b.write_byte_data(LIGHT_ADDR, 0x18, 0x01) # reset the chip
        time.sleep(0.02)
        b.write_byte_data(LIGHT_ADDR, 0x07, 0x17) # unlock key from the datasheet
        time.sleep(0.02)
        b.write_byte_data(LIGHT_ADDR, 0x17, 0x30) # measure visible + infrared
        b.write_byte_data(LIGHT_ADDR, 0x18, 0xA1) # store that choice in the chip
        time.sleep(0.02)
        self.light_ready = True

    def pir(self):
        return self.grovepi.digitalRead(PIR_PORT) # 1 = motion

    def button(self):
        return self.grovepi.digitalRead(BUTTON_PORT) # 1 = pressed

    def led(self, level):
        self.grovepi.digitalWrite(LED_PORT, level) # 1 = on, 0 = off

    def ir(self):
        try:
            if not self.light_ready:
                self._setup_light()
            self.bus.write_byte_data(LIGHT_ADDR, 0x18, 0x06) # take one measurement
            time.sleep(0.1) # wait for it
            return self.bus.read_word_data(LIGHT_ADDR, 0x24) # infrared result
        except OSError:
            self.light_ready = False # set the chip up again next time
            raise


class SimHardware(object):
    """Fake sensors that follow a script, to test the logic without a Pi."""

    def __init__(self):
        self.t0 = time.time()
        log("[sim] script: motion+mail 5-9s | PIR errors 20-24s | button 30s | motion, no mail 40-42s")

    def _t(self):
        return time.time() - self.t0

    def pir(self):
        t = self._t()
        if 20 <= t < 24:
            raise OSError("fake I2C glitch")
        return 1 if (5 <= t < 9) or (40 <= t < 42) else 0

    def button(self):
        return 1 if 30 <= self._t() < 30.4 else 0

    def led(self, level):
        pass

    def ir(self):
        base = 260 if 7 <= self._t() < 29 else 280 # mail covers the sensor from 7 s to 29 s
        return base + random.randint(-2, 2)


def try_call(fn, *args):
    """Call a hardware function, retrying 3 times on I2C trouble. Returns (ok, value)."""
    for _ in range(3):
        try:
            return True, fn(*args)
        except OSError:
            time.sleep(0.05)
    return False, None


def average_ir(hw, n):
    """Average n infrared readings. Returns None if too many of them failed."""
    values = []
    for _ in range(n):
        ok, v = try_call(hw.ir)
        if ok:
            values.append(v)
    if len(values) < max(1, n // 2):
        return None
    return sum(values) / float(len(values))


def led_level(pattern, now):
    """Is the LED on (1) or off (0) right now for this pattern?"""
    if pattern == "solid":
        return 1
    if pattern == "slow": # 0.5 s on, 0.5 s off
        return 1 if (now % 1.0) < 0.5 else 0
    if pattern == "fast": # 0.15 s on, 0.15 s off
        return 1 if (now % 0.3) < 0.15 else 0
    if pattern == "error": # two quick blinks, then a pause
        t = now % 2.0
        return 1 if (t < 0.15 or 0.3 <= t < 0.45) else 0
    return 0


def main():
    hw = SimHardware() if SIMULATE else RealHardware()
    log("started" + (" (simulation)" if SIMULATE else ""))
    log("starting up: PIR warms up for %d s. Keep the box EMPTY." % WARMUP_S)

    # state the loop keeps track of
    ready = False # False while starting up (slow blink)
    baseline = None # empty-box infrared reading
    mail = False # True while mail is believed to be in the box
    pir_since = None # when the PIR last went HIGH
    last_motion = 0.0 # last time motion was seen
    motion_active = False # True from "motion confirmed" until the mail check
    fast_until = 0.0  # fast-blink the LED until this time
    button_prev = 0 # previous button state, to detect a new press
    fails = 0 # consecutive loops where the PIR or button could not be read
    light_bad = False # True while the light sensor cannot be read
    pattern_prev = None
    led_prev = None

    try:
        while True:
            now = time.time()
            if not ready:
                if now - START >= WARMUP_S:
                    baseline = average_ir(hw, 20)
                    if baseline is None:
                        light_bad = True
                        log("cannot read the light sensor, will keep trying")
                    else:
                        light_bad = False
                        log("baseline (empty box) IR = %.1f" % baseline)
                        ready = True
                        log("ready")
                    time.sleep(1.0)

            ok_pir, pir = try_call(hw.pir)
            ok_btn, btn = try_call(hw.button)
            fails = 0 if (ok_pir and ok_btn) else fails + 1

            if ready:
                if ok_pir:
                    if pir == 1:
                        if pir_since is None:
                            pir_since = now
                        if motion_active:
                            last_motion = now
                        elif now - pir_since >= MOTION_CONFIRM_S:
                            motion_active = True
                            last_motion = now
                            fast_until = now + FAST_BLINK_S
                            log("MOTION detected")
                    else:
                        pir_since = None
                    if motion_active and pir == 0 and now - last_motion >= SETTLE_S:
                        motion_active = False
                        avg = average_ir(hw, SAMPLES)
                        if avg is None:
                            light_bad = True
                            log("mail check skipped: cannot read the light sensor")
                        else:
                            light_bad = False
                            drop = baseline - avg
                            log("mail check: IR %.1f, baseline %.1f, drop %.1f" % (avg, baseline, drop))
                            if not mail and drop >= MAIL_DROP:
                                mail = True
                                log("MAIL in the box")
                            elif mail and drop <= MAIL_CLEAR:
                                mail = False
                                log("box looks empty again")
                if ok_btn:
                    if btn == 1 and button_prev == 0: # a NEW press, not a held button
                        log("BUTTON: clearing mail state and re-measuring the empty box")
                        mail = False
                        time.sleep(1.0)
                        new_base = average_ir(hw, 20)
                        if new_base is None:
                            light_bad = True
                            log("could not re-measure, keeping the old baseline")
                        else:
                            baseline = new_base
                            light_bad = False
                            log("new baseline IR = %.1f" % baseline)
                    button_prev = btn
            error = fails >= ERROR_AFTER or light_bad
            if error:
                pattern = "error"
            elif not ready:
                pattern = "slow"
            elif now < fast_until:
                pattern = "fast"
            else:
                pattern = "solid"

            if pattern != pattern_prev:
                log("LED: %s" % pattern)
                pattern_prev = pattern

            level = led_level(pattern, now)
            if level != led_prev:
                ok_led, _ = try_call(hw.led, level)
                if ok_led:
                    led_prev = level

            time.sleep(LOOP_S)

    except KeyboardInterrupt:
        log("stopping")
    finally:
        try_call(hw.led, 0)


if __name__ == "__main__":
    main()
