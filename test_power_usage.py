# Test very approximate power / energy usage in different sleep modes
# Using MAX1704x battery gauge reported % battery capacity

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

sleep_mode = 1  # S0 = no sleep, S1 = only turn off display / I2C, S2 = also microprocessor light sleep, S3 = also microprocessor deep sleep

# Battery monitor
monitor = adafruit_max1704x.MAX17048(board.I2C())

# Configure inputs
# D0: wake-from-sleep (active low)
button_D0 = digitalio.DigitalInOut(board.D0)
button_D0.switch_to_input(pull=digitalio.Pull.UP)
# D1: change sleep mode
button_D1 = digitalio.DigitalInOut(board.D1)
button_D1.switch_to_input(pull=digitalio.Pull.DOWN)
# D2: go to sleep
button_D2 = digitalio.DigitalInOut(board.D2)
button_D2.switch_to_input(pull=digitalio.Pull.DOWN)

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
text_D0 = displayio.Group(scale=2, x=0, y=10)
text_D0.append(label.Label(terminalio.FONT, text="< WAKE", color=0xFFFFFF))
display_group.append(text_D0)

text_D1 = displayio.Group(scale=2, x=0, y=display.height // 2)
text_D1.append(label.Label(terminalio.FONT, text=f"< MODE{sleep_mode}", color=0xFFFFFF))
display_group.append(text_D1)

text_D2 = displayio.Group(scale=2, x=0, y=display.height - 10)
text_D2.append(label.Label(terminalio.FONT, text=f"< SLEEP", color=0xFFFFFF))
display_group.append(text_D2)


# Battery level text
text_bat = displayio.Group(scale=2, x=100, y=10)
text_bat.append(label.Label(terminalio.FONT, text=f"{monitor.cell_percent:.1f}%", color=0xFFFF00))
display_group.append(text_bat)
# Battery usage text
text_usage = displayio.Group(scale=2, x=100, y=50)
text_usage.append(label.Label(terminalio.FONT, text="-xx.x% bat\nin xxxx s\n~xx.xx mA avg", color=0xFFFF00))
display_group.append(text_usage)

low_power_mode = False


def enter_low_power():
    global low_power_mode
    low_power_mode = True
    tft_i2c_power.value = False


def exit_low_power():
    global low_power_mode
    low_power_mode = False
    tft_i2c_power.value = True


def compute_and_display_sleep_usage():
    global text_usage
    postsleep_battery_percent = monitor.cell_percent
    postsleep_time_int = time.time()
    bat_delta_pct = postsleep_battery_percent - presleep_battery_percent
    bat_delta_mAh = (bat_delta_pct / 100) * 420  # 420 mAh battery
    time_delta = postsleep_time_int - presleep_time_int
    avg_bat_mA = abs(bat_delta_mAh / (time_delta / 3600))
    if bat_delta_mAh > 0: # should not be positive-- may be sign we're plugged in: data invalid
        text = f"err% bat\nin {time_delta:.0f}s\n~??.?? mA avg"
    else:
        text = f"{bat_delta_pct:.1f}% bat\nin {time_delta:.0f}s\n~{avg_bat_mA:.2f}mA avg"
    text_usage[0].text = text


# if we just woke up from a deep sleep and reboot, load some config values from backup RAM / sleep memory
#  and display computed usage
if alarm.wake_alarm:
    # todo: implement saving of last battery % and times here in byte array?
    presleep_battery_percent = (256 * alarm.sleep_memory[0] + alarm.sleep_memory[1]) / 10
    # hacky conversion of 4 bytes of data to a 32-bit timer value
    presleep_time_int = (
        256 * 256 * 256 * alarm.sleep_memory[2]
        + 256 * 256 * alarm.sleep_memory[3]
        + 256 * alarm.sleep_memory[4]
        + alarm.sleep_memory[5]
    )
    sleep_mode = alarm.sleep_memory[6]
    text_D1[0].text = f"< MODE{sleep_mode}"
    compute_and_display_sleep_usage()

while True:
    # D0: wake (note: since D0 is active low, we 'not value' means it is pressed)
    if not button_D0.value:
        exit_low_power()
        compute_and_display_sleep_usage()
    if not low_power_mode:
        # update battery text (but not if in low power mode with display off)
        text_bat[0].text = f"{monitor.cell_percent:.1f}%"
        # D1: change sleep mode
        if button_D1.value:
            sleep_mode = (sleep_mode + 1) % 4
            text_D1[0].text = f"< MODE{sleep_mode}"
            while button_D1.value:
                pass  # wait until it's no longer pressed
        # D2: sleep (details depend on mode)
        if button_D2.value:
            presleep_battery_percent = monitor.cell_percent
            presleep_time_int = time.time()
            # In any sleep mode except S0, turn off the display and I2C
            if sleep_mode >= 1:
                enter_low_power()
            # in more advanced sleep modes, sleep microprocessor undil D0 pressed
            # Sleep Mode 2: light sleep
            if sleep_mode == 2:
                button_D0.deinit()
                pin_alarm = alarm.pin.PinAlarm(pin=board.D0, value=False, pull=True)
                alarm.light_sleep_until_alarms(pin_alarm)
                # after sleep ends
                # reinitialize button
                button_D0 = digitalio.DigitalInOut(board.D0)
                button_D0.switch_to_input(pull=digitalio.Pull.UP)
                exit_low_power()
                compute_and_display_sleep_usage()
            # Sleep Mode 3: deep sleep
            if sleep_mode == 3:
                button_D0.deinit()
                pin_alarm = alarm.pin.PinAlarm(pin=board.D0, value=False, pull=True)
                # save a few key status values to backup RAM ('sleep memory') to reload after deep sleep reboot
                battery_pct_fixedpoint = int(presleep_battery_percent * 10)
                alarm.sleep_memory[0] = battery_pct_fixedpoint // 256
                alarm.sleep_memory[1] = battery_pct_fixedpoint % 256
                # quick hack to convert 32-bit time to four bytes
                alarm.sleep_memory[2] = presleep_time_int // (256 * 256 * 256)
                presleep_time_int %= 256 * 256 * 256
                alarm.sleep_memory[3] = presleep_time_int // (256 * 256)
                presleep_time_int %= 256 * 256
                alarm.sleep_memory[4] = presleep_time_int // 256
                alarm.sleep_memory[5] = presleep_time_int % 256
                alarm.sleep_memory[6] = sleep_mode
                alarm.exit_and_deep_sleep_until_alarms(pin_alarm)
                # note: never reaches this line (processor reboots after wake from deep sleep, see if alarm.wake: line earlier)
            while button_D2.value:
                pass  # wait until D2 not pressed to return to main loop and accept new input
    # loop after sleeping
    time.sleep(0.05)
