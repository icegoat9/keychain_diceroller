# Test approximate power / energy usage in different sleep modes via sleep, wake, and report over (serial, etc)
# Using MAX1704x battery gauge reported % battery capacity

# Log to flash by holding down D2 during boot (and installing the matching boot.py -- see datalogger_boot.py)

import alarm
import board
import displayio
import terminalio
import time
import digitalio

# For imports below here, need to copy the libraries from the circuitpython bundle to the local lib/ folder
from adafruit_display_text import label
import adafruit_max1704x

# does importing wifi let us shut it off? (didn't make an obvious battery difference, though...)
# import wifi
# wifi.radio.enabled = False

sleep_mode = 3  # S0 = no sleep, S1 = only turn off display / I2C, S2 = also microprocessor light sleep, S3 = also microprocessor deep sleep, S4 = hybrid (n/a)
SLEEP_TIME = 3600  # wake after ## seconds sleep and log battery level
WAKE_TIME = 1  # after waking for ## seconds (w/ display on), go to sleep

# Battery monitor
monitor = adafruit_max1704x.MAX17048(board.I2C())

# Configure inputs
# D0: wake-from-sleep (active low)
# button_D0 = digitalio.DigitalInOut(board.D0)
# button_D0.switch_to_input(pull=digitalio.Pull.UP)
# D1: change sleep mode
button_D1 = digitalio.DigitalInOut(board.D1)
button_D1.switch_to_input(pull=digitalio.Pull.DOWN)
# D2: was used during boot to enable storage...
# button_D2 = digitalio.DigitalInOut(board.D2)
# button_D2.switch_to_input(pull=digitalio.Pull.DOWN)

# basic board LED
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

# Disable Neopixel to save power
neopixel_power = digitalio.DigitalInOut(board.NEOPIXEL_POWER)
neopixel_power.direction = digitalio.Direction.OUTPUT
neopixel_power.value = False

# Prepare to disable TFT (and Stemma QT) to save power
tft_i2c_power = digitalio.DigitalInOut(board.TFT_I2C_POWER)
tft_i2c_power.direction = digitalio.Direction.OUTPUT
tft_i2c_power.value = True  # unnecessary as defaults on, but we can set to False to save power
low_power_mode = False

# Display setup
display = board.DISPLAY
display_group = displayio.Group()
display.root_group = display_group

# Menu text
# text_D0 = displayio.Group(scale=2, x=0, y=10)
# text_D0.append(label.Label(terminalio.FONT, text="< WAKE", color=0xFFFFFF))
# display_group.append(text_D0)

text_D1 = displayio.Group(scale=2, x=0, y=display.height // 2)
text_D1.append(label.Label(terminalio.FONT, text=f"< MODE{sleep_mode}", color=0xFFFFFF))
display_group.append(text_D1)

text_cycle = displayio.Group(scale=2, x=100, y=display.height // 2)
text_cycle.append(label.Label(terminalio.FONT, text=f"wake {WAKE_TIME}s, \nsleep {SLEEP_TIME}s", color=0xFFFFFF))
display_group.append(text_cycle)

# Battery level text
text_bat = displayio.Group(scale=2, x=100, y=10)
text_bat.append(label.Label(terminalio.FONT, text=f"{monitor.cell_percent:.1f}%", color=0xFFFF00))
display_group.append(text_bat)

low_power_mode = False


def enter_low_power():
    global low_power_mode
    low_power_mode = True
    tft_i2c_power.value = False


def exit_low_power():
    global low_power_mode
    low_power_mode = False
    tft_i2c_power.value = True


def log_battery_level():
    try:
        with open(f"/battery_log_{sleep_mode}.txt", "a") as log:
            # write time in seconds and cell percent to file
            log.write(f"{sleep_mode},{time.time()},{monitor.cell_percent}\n")
            log.flush()
            led.value = True
            time.sleep(0.1)
            led.value = False
    except OSError as e:  # Filesystem not writable by CircuitPython...
        print("error writing to filesystem")
        led.value = True
        time.sleep(1)
        led.value = False


lastsleep = time.time()

# if we just woke up from a deep sleep and reboot reset sleep mode from saved value
if alarm.wake_alarm:
    sleep_mode = alarm.sleep_memory[0]
    text_D1[0].text = f"< MODE{sleep_mode}"

# log battery level on startup (including if we just woke from a deep sleep and reboot)
log_battery_level()

while True:
    if not low_power_mode:
        # update battery text (but not if in low power mode with display off)
        text_bat[0].text = f"{monitor.cell_percent:.1f}%"
        # D1: change sleep mode
        if button_D1.value:
            sleep_mode = (sleep_mode + 1) % 4
            text_D1[0].text = f"< MODE{sleep_mode}"
            while button_D1.value:
                pass  # wait until it's no longer pressed
        # sleep on timer
        if (time.time() - lastsleep) > WAKE_TIME:
            # go to sleep
            lastsleep = time.time()
            # In any sleep mode except S0, turn off the display and I2C
            if sleep_mode >= 1:
                enter_low_power()
            # in more advanced sleep modes, sleep microprocessor
            # Sleep Mode 2: light sleep
            if sleep_mode == 2:
                pin_alarm = alarm.pin.PinAlarm(pin=board.D0, value=False, pull=True)
                time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + SLEEP_TIME)
                # Sleep with both time and pin alarms for more realistic power draw (pin alarm is what end app uses and draws more power)
                alarm.light_sleep_until_alarms(time_alarm, pin_alarm)
                # after sleep ends
                exit_low_power()
                lastsleep = time.time()
                log_battery_level()
            # Sleep Mode 3: deep sleep
            if sleep_mode == 3:
                pin_alarm = alarm.pin.PinAlarm(pin=board.D0, value=False, pull=True)
                time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + SLEEP_TIME)
                alarm.sleep_memory[0] = sleep_mode
                # Sleep with both time and pin alarms for more realistic power draw (pin alarm is what end app uses and draws more power)
                alarm.exit_and_deep_sleep_until_alarms(time_alarm, pin_alarm)
                # note: never reaches this line (processor reboots after wake from deep sleep, see if alarm.wake: line earlier)
    elif low_power_mode:  # only for sleep mode 1
        if (time.time() - lastsleep) > SLEEP_TIME:
            exit_low_power()
            lastsleep = time.time()
            log_battery_level()
    # loop after sleeping
    time.sleep(0.05)
