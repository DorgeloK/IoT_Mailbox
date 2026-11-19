# TEST 4 (correct sensor): Grove Sunlight Sensor (Si1145 chip) on an I2C port
# The Si1145 always uses I2C address 0x60. `i2cdetect -y 1` should show "60".

import smbus              # I2C library (the GrovePi library already uses it)
import time               # pauses

ADDR = 0x60               # fixed I2C address of the Si1145

bus = smbus.SMBus(1)      # I2C bus 1 on the Pi

# Register numbers from the Si1145 datasheet
REG_PARTID  = 0x00        # chip ID (should read 0x45 for an Si1145)
REG_HWKEY   = 0x07        # must be set to 0x17 to unlock normal operation
REG_PARAMWR = 0x17        # value to write into an internal parameter
REG_COMMAND = 0x18        # where commands are sent to the chip
REG_ALSVIS  = 0x22        # visible light result (2 bytes, low byte first)
REG_ALSIR   = 0x24        # infrared light result (2 bytes, low byte first)
REG_PARAMRD = 0x2E        # reads back the parameter we just set

CMD_RESET     = 0x01      # reset the chip
CMD_PARAM_SET = 0xA0      # "set a parameter" (the parameter number is added to this)
CMD_ALS_FORCE = 0x06      # "take one light measurement now"
PARAM_CHLIST  = 0x01      # parameter that chooses which channels are measured

# 1. Check that the right chip answers
part_id = bus.read_byte_data(ADDR, REG_PARTID)
print("Part ID:", hex(part_id), "(0x45 means Si1145, 0x46 or 0x47 are close relatives)")

# 2. Reset and unlock the chip
bus.write_byte_data(ADDR, REG_COMMAND, CMD_RESET)   # reset to a known state
time.sleep(0.02)                                    # give it time to restart
bus.write_byte_data(ADDR, REG_HWKEY, 0x17)          # unlock with the key value from the datasheet
time.sleep(0.02)

# 3. Turn on the visible (0x10) and infrared (0x20) channels
bus.write_byte_data(ADDR, REG_PARAMWR, 0x30)                    # 0x10 + 0x20 = 0x30
bus.write_byte_data(ADDR, REG_COMMAND, CMD_PARAM_SET | PARAM_CHLIST)  # store it in the channel-list parameter
time.sleep(0.02)
echo = bus.read_byte_data(ADDR, REG_PARAMRD)       # the chip echoes back what it stored
print("Channel list readback:", hex(echo), "(should be 0x30)")

print("Reading light. Cover the sensor, then shine a phone torch at it. (Ctrl+C to quit)")

while True:
    try:
        bus.write_byte_data(ADDR, REG_COMMAND, CMD_ALS_FORCE)  # ask for one measurement
        time.sleep(0.1)                                        # wait for it to finish
        vis = bus.read_word_data(ADDR, REG_ALSVIS)             # visible light value
        ir = bus.read_word_data(ADDR, REG_ALSIR)               # infrared light value
        print("Visible:", vis, "  Infrared:", ir)
        time.sleep(0.4)
    except IOError:
        print("I2C error: check the cable is in an I2C port")
        time.sleep(1)

# What to do with the numbers: write down the Visible value with the box empty and with an
# envelope covering the sensor. Your mail threshold goes between them.
# Note: this chip shows a small baseline value (a few hundred) even in the dark. That is normal.
