# Test I2C (MAX 1704x) as well as i2c error
import board
import time
import digitalio

# For imports below here, need to copy the libraries from the circuitpython bundle to the local lib/ folder
import adafruit_max1704x

print("test_i2c.py:")

# Battery monitor
monitor = adafruit_max1704x.MAX17048(board.I2C())

# Prepare to disable TFT (and Stemma QT and I2C battery monitor) to save power and cause error
tft_i2c_power = digitalio.DigitalInOut(board.TFT_I2C_POWER)
tft_i2c_power.direction = digitalio.Direction.OUTPUT
tft_i2c_power.value = True  # unnecessary as defaults on, but we can set to False to save power

loop = 1

while True:
    try:
        print(f"I2C battery monitor test: V={monitor.cell_voltage}, %charge={monitor.cell_percent}")
    except:
        print("Expected i2c comms error on 3rd read only")
    time.sleep(1)
    loop += 1
    if loop == 3:
        # should cause error on next i2c read
        tft_i2c_power.value = False
    elif loop > 3:
        tft_i2c_power.value = True
