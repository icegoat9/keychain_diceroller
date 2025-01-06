# Version of main program where D2 button cycles through different sleep modes for experimentation
#  (this originally was the main program but I'm stripping this functionality out)
#  diceroll.py may have more up to date main code, will keep this around for sleep mode tests

# Roll virtual die on Feather (ESP32-S3 + SPI TFT display + battery)
# https://github.com/icegoat9/diceroll_feather

import alarm
import board
import displayio
import terminalio
import random
import time
import digitalio
import math
import vectorio

# For imports below here, need to copy the libraries from the circuitpython bundle to the local lib/ folder
from adafruit_display_text import label
import adafruit_max1704x

# does importing wifi let us shut it off? (didn't make an obvious battery difference, though...)
# import wifi
# wifi.radio.enabled = False

TFT_BRIGHTNESS = 0.5
TFT_DIM_BRIGHTNESS = 0.1
# handle dimming and sleeping after inactivity
INACTIVITY_DIM_TIME = 10
INACTIVITY_SLEEP_TIME = 15
INACTIVITY_DEEPSLEEP_TIME = 180  # the main power saving measure...

battery_icon_mode = True

# Disable Neopixel to save power
neopixel_power = digitalio.DigitalInOut(board.NEOPIXEL_POWER)
neopixel_power.direction = digitalio.Direction.OUTPUT
neopixel_power.value = False

# Prepare to disable TFT (and Stemma QT) to save power
tft_i2c_power = digitalio.DigitalInOut(board.TFT_I2C_POWER)
tft_i2c_power.direction = digitalio.Direction.OUTPUT
# tft_i2c_power.value = False  # initially powered down, but will power up shortly
tft_i2c_power.value = True  # power up display and I2C (already on by default...)
low_power_mode = False

dice_types = [
    {"sides": 3, "zero_index": False, "polygon_sides": 3, "poly_r0": 0, "symbol_list": ["-", "O", "+"]},
    {"sides": 6, "zero_index": False, "polygon_sides": 4, "poly_r0": 45},
    #    {"sides": 6, "number": 2, "zero_index": False},
    {"sides": 10, "zero_index": True, "polygon_sides": 5, "poly_r0": 54},  # return 0-9, not 1-10
    {"sides": 20, "zero_index": False, "polygon_sides": 6, "poly_r0": 0},
    {"sides": 100, "zero_index": True, "polygon_sides": 10, "poly_r0": 0},
]

dice_index = 3  # D20

sleep_mode = 4  # 0 = none, 1 = display/I2C only, 2 = ESP32 light sleep, 3 = ESP32 deep sleep, 4 = hybrid (display off, then deep sleep after longer period)
polygon_rotation = 0  # 0 to 360...
animation_running = False  # is a die roll currently animating?
animation_time = 0.5

# if we just woke up from a deep sleep and reboot, load some config values from backup RAM / sleep memory
if alarm.wake_alarm:
    sleep_mode = alarm.sleep_memory[0]
    dice_index = alarm.sleep_memory[1]

# Battery monitor
monitor = adafruit_max1704x.MAX17048(board.I2C())

# Configure three input buttons
button_D0 = digitalio.DigitalInOut(board.D0)
button_D0.switch_to_input(pull=digitalio.Pull.UP)
button_D1 = digitalio.DigitalInOut(board.D1)
button_D1.switch_to_input(pull=digitalio.Pull.DOWN)
button_D2 = digitalio.DigitalInOut(board.D2)
button_D2.switch_to_input(pull=digitalio.Pull.DOWN)

# board-specific display initialization (for this S3 TFT Feather)
display = board.DISPLAY
display.brightness = TFT_BRIGHTNESS

def button_pressed(n):
    """Check if button N is pressed (implemented differently for D0 vs. D1/D2 due to board pullups vs pulldowns)"""
    if n == 0:
        # D0 is pulled HIGH by default on S3 Reverse TFT Feather (see docs)
        return not button_D0.value
    elif n == 1:
        return button_D1.value
    elif n == 2:
        return button_D2.value
    else:
        raise ValueError(f"No such button #{n}")


def any_button_pressed():
    return button_pressed(0) or button_pressed(1) or button_pressed(2)

# initial polygon configuration to minimize computation needed in the
#  generate_polygon_pts() call below
# WIP and TBD if this speeds it (is this math bottleneck or display interface?)
# TODO: copy much of this into a function called when we switch # of polygon sides and on startup...
# TODO: change this to a dict indexed by rotation angle [5], [10], etc?
# TODO: could generate different rotation densities per die type (e.g. large # side polygons rotate faster)
poly_radius_default = display.height / 2
poly_radius = poly_radius_default   # different if scaled
# configure only on change of number of sides in polygon
poly_sides = dice_types[dice_index]["sides"]
poly_sidelen = math.pi * display.height / (1.2 * poly_sides)  # approximation
poly_angle_internal = 360 / poly_sides
poly_pts_lookup = []
# generate a list of the N polygon verticies for all possible 5 degree initial rotation values?
for i in range(360/5):
    poly_pts = []
    for j in range(poly_sides):
        an = math.radians(5 * i + poly_angle_internal * j)
        x = poly_radius * math.cos(an)
        y = poly_radius * math.sin(an)
        poly_pts.append((int(round(x)), int(round(y))))
    poly_pts_lookup.append(poly_pts)

def lookup_polygon_pts(rotation=0):
    """Calculate vertices of polygon-- lookup a precomputed set for current polygon type, for given rotation."""
    return poly_pts_lookup[rotation // 5]


def generate_polygon_pts(n, rotation=0, scale=None, x_offset=0, y_offset=0):
    """Calculate vertices of polygon with N sides."""
    # TODO: don't re-calculate all of these every time called if slow,
    #       can pre-calculate some only when we change dice?
    if scale:
        poly_radius = scale * poly_radius_default
    else:
        poly_radius = poly_radius_default
    sidelen = math.pi * display.height / (1.2 * n)  # approximation
    angle_internal = 360 / n
    # let's have angles read clockwise from the +X axis
    pts = []
    for i in range(n):
        an = math.radians(rotation + angle_internal * i)
        x = poly_radius * math.cos(an)
        y = poly_radius * math.sin(an)
        pts.append((int(round(x + x_offset)), int(round(y + y_offset))))
    return pts


def rolldie(dietype) -> str:
    """Roll the die specified by the data structure dietype (typically an item from dice_types[]), return string result."""
    n = random.randint(1, dietype["sides"])
    if dietype["zero_index"] or "symbol_list" in dietype:
        n -= 1
    if "symbol_list" in dietype:
        return dietype["symbol_list"][n]
    return str(n)


def rolldie_OBSOLETE():
    """Roll the die type specified by dice_index, return result number."""
    die = dice_types[dice_index]
    n = random.randint(1, die["sides"])
    if die["zero_index"] or "symbol_list" in die:
        n -= 1
    return n


def roll_to_string_OBSOLETE(n):
    """Convert roll number to string"""
    die = dice_types[dice_index]
    if "symbol_list" in die:
        return die["symbol_list"][n]
    return str(n)



# Create an image group we can add elements to, and add that group to the display
# The display will now automatically handle updating the screen with all objects in this group
display_group = displayio.Group()
display.root_group = display_group

# TODO: determine if this is needed or not since it's all black
# Next we create a Bitmap which is like a canvas that we can draw on.
# We create a Palette with one color and set that color to a value
canvas = displayio.Bitmap(display.width, display.height, 1)
# TODO: (?) -- combine the following three lines into two or even one if possible for compactness?
# TODO: rename all these with some common prefix such as obj_ or layer_ or gfx_, to make later editing of these globals more clear?
background_palette = displayio.Palette(1)
background = 0x000000  # Black
background_palette[0] = background
# With all those pieces in place, we create a TileGrid by passing the bitmap and palette and draw it at (0, 0) which represents the display's upper left.
background = displayio.TileGrid(canvas, pixel_shader=background_palette, x=0, y=0)
display_group.append(background)

# Now draw the dice background (filled polygon) on the right
DIEROLL_X0 = display.width - display.height
# border = 10  # TODO: add a contasting border? But would slow down rendering
poly_palette = displayio.Palette(1)
poly_palette[0] = 0xCF50FA  # purple
current_die = dice_types[dice_index]
poly_points = generate_polygon_pts(current_die["polygon_sides"], rotation=current_die["poly_r0"])
polygon = vectorio.Polygon(
    pixel_shader=poly_palette, points=poly_points, x=DIEROLL_X0 + display.height // 2, y=display.height // 2
)
display_group.append(polygon)


# initial dice value (and do a first roll on startup or resume from deep sleep)
def roll_die_and_update_display():
    text_roll[0].text = rolldie(dice_types[dice_index])
    # note: bounding_box = (x, y, width, height)
    text_width = text_roll_area.bounding_box[2] * DIE_TEXT_SCALE
    text_roll.x = DIEROLL_X0 + display.height // 2 - text_width // 2

def clear_die_display():
    text_roll[0].text = ""


DIE_TEXT_SCALE = 6
text_roll_color = 0x000000
text_roll_area = label.Label(terminalio.FONT, text="??", color=text_roll_color)
text_width = text_roll_area.bounding_box[2] * DIE_TEXT_SCALE
text_roll = displayio.Group(
    scale=DIE_TEXT_SCALE, x=DIEROLL_X0 + display.height // 2 - text_width // 2 + 6, y=display.height // 2
)
text_roll.append(text_roll_area)
display_group.append(text_roll)
roll_die_and_update_display()

# Menu block and text
text_D0 = displayio.Group(scale=2, x=0, y=10)
text = "< ROLL"
text_area = label.Label(terminalio.FONT, text=text, color=0xFFFFFF)
text_D0.append(text_area)
display_group.append(text_D0)

text_D1 = displayio.Group(scale=2, x=0, y=display.height // 2)
text = "< D?"
text_area = label.Label(terminalio.FONT, text=text, color=0xFFFFFF)
text_D1.append(text_area)
display_group.append(text_D1)


def get_battery_str():
    #    try:
    pct = monitor.cell_percent
    pct = max(0, min(100, pct))
    return f"{pct:.1f}%"


def get_battery():
    """Return battery %, clamped from 0 to 100"""
    return max(0, min(100, monitor.cell_percent))


def get_battery_color(pct):
    if pct <= 20:
        return 0xFF0000  # red
    elif pct <= 80:
        return 0xFFFF00  # yellow
    else:
        return 0x00FF00  # green


bat_level = get_battery()  # - random.randint(0,100)  # temporary random # for testing range of values
bat_color = get_battery_color(bat_level)

# Battery level text (not shown by default, see .hidden below)
text_bat = displayio.Group(scale=2, x=30, y=display.height - 15)
text_info_color = 0xFFFF00  # Yellow
text_area = label.Label(terminalio.FONT, text=f"{bat_level:.0f}%", color=text_info_color)
text_bat.append(text_area)

# Sleep mode text
text_sleep = displayio.Group(scale=2, x=0, y=display.height - 15)
text_area = label.Label(terminalio.FONT, text=f"S{sleep_mode}", color=text_info_color)
text_sleep.append(text_area)

display_group.append(text_bat)
display_group.append(text_sleep)

# Battery visual icon

# Draw frame of battery as filled polygon
BH = 15  # battery icon height
BW = 35  # battery icon width
BS = BH // 3  # battery step
BG = 2  # battery gap
bat_icon_palette = displayio.Palette(1)
bat_icon_palette[0] = bat_color
bat_icon_frame = vectorio.Polygon(
    pixel_shader=bat_icon_palette,
    points=[
        (0, 0),
        (BW - BS, 0),
        (BW - BS, BS),
        (BW, BS),
        (BW, BS * 2),
        (BW - BS, BS * 2),
        (BW - BS, BS * 3),
        (0, BS * 3),
    ],
    x=0,
    y=display.height - BH,
)

# now clear out part of the battery w/ a black rectangle
black_palette = displayio.Palette(1)
black_palette[0] = 0x000000
fill_width = max(1, int((BW - BS - 2 * BG) * (100 - bat_level) / 100))
bat_icon_filling = vectorio.Rectangle(
    pixel_shader=black_palette,
    width=fill_width,
    height=BH - 2 * BG,
    x=BW - BS - BG - fill_width,
    y=display.height - BH + BG,
)
display_group.append(bat_icon_frame)
display_group.append(bat_icon_filling)


def set_battery_icon_mode(iconmode):
    """Show and hide icon vs. text/debug representation of battery"""
    global battery_icon_mode
    battery_icon_mode = iconmode
    if iconmode:
        text_bat.hidden = True
        text_sleep.hidden = True
        bat_icon_frame.hidden = False
        bat_icon_filling.hidden = False
    else:
        text_bat.hidden = False
        text_sleep.hidden = False
        bat_icon_frame.hidden = True
        bat_icon_filling.hidden = True


set_battery_icon_mode(battery_icon_mode)

text_D1[0].text = f"< D{dice_types[dice_index]['sides']}"


def enter_low_power():
    global low_power_mode
    low_power_mode = True
    tft_i2c_power.value = False


def exit_low_power():
    global low_power_mode
    low_power_mode = False
    tft_i2c_power.value = True
    set_battery_icon_mode(True)


# handle dimming and sleeping after periods of inactivity
last_button_time = time.monotonic()


def deep_sleep():
    # save a few key status values to backup RAM ('sleep memory') to reload after deep sleep reboot
    alarm.sleep_memory[0] = sleep_mode
    alarm.sleep_memory[1] = dice_index
    button_D0.deinit()
    pin_alarm = alarm.pin.PinAlarm(pin=board.D0, value=False, pull=True)
    alarm.exit_and_deep_sleep_until_alarms(pin_alarm)
    # will never reach this point: reboots after exiting deep sleep

# roll the die on startup (or wake from deep sleep)
# TODO: abstract this and the calling of it below?
animation_running = True
animation_ticks = 0
animation_t0 = time.monotonic()

def debounce_buttons():
    global debounce_D1
    if not button_pressed(1):
        debounce_D1 = False

debounce_D1 = False

# main program loop
while True:
    # D2 = change from battery icon mode to debug mode, and if in debug mode, change sleep mode (for testing, may remove)
    if button_pressed(2):
        if battery_icon_mode:
            set_battery_icon_mode(False)
        else:
            # if in debug mode, cycle through sleep modes
            sleep_mode = (sleep_mode + 1) % 5
            text_sleep[0].text = f"S{sleep_mode}"
        while button_pressed(2):
            pass  # wait until button is released
        display.brightness = TFT_BRIGHTNESS
        last_button_time = time.monotonic()
    if low_power_mode:
        # in hybrid sleep mode 4, automatically deep sleep after N seconds in light sleep
        if sleep_mode == 4 and (time.monotonic() - last_button_time) > INACTIVITY_DEEPSLEEP_TIME:
            deep_sleep()
            # should not ever return to this location: will reboot at end of deep sleep
            raise RuntimeError("deep sleep did not restart on wake as expected")
        if any_button_pressed():
            exit_low_power()
            display.brightness = TFT_BRIGHTNESS
            set_battery_icon_mode(True)
            while button_pressed(1) or button_pressed(2):
                pass  # wait until D1 or D2 released, but D0 will trigger a new roll, below
            last_button_time = time.monotonic()  # reset sleep timer to current time
    # Standard main loop, skip if in low power mode
    if not low_power_mode:
        if animation_running:
            # While animating a die roll, skip most other main loop code for speed, though can still check for changing dice
            polygon_rotation = (polygon_rotation + 10) % 360
            polygon.points = generate_polygon_pts(dice_types[dice_index]["polygon_sides"], rotation=polygon_rotation)
            # only update number every N animation cycles
            if (animation_ticks % 2) == 0:
                roll_die_and_update_display()
            animation_ticks += 1
            if time.monotonic() - animation_t0 > animation_time:
                animation_running = False
                while button_pressed(0):
                    pass  # wait until D0 released if not already
        else:
            if any_button_pressed():
                display.brightness = TFT_BRIGHTNESS
                last_button_time = time.monotonic()
            if button_pressed(0):
                # roll die on roll button or changing of # sides
                animation_running = True
                animation_ticks = 0
                animation_t0 = time.monotonic()
            # Update battery level display
            text_bat[0].text = get_battery_str()
            # If no button has been pressed in a while, turn off display and I2C to save battery
            if sleep_mode >= 1:
                if (time.monotonic() - last_button_time) > INACTIVITY_SLEEP_TIME:
                    enter_low_power()
                    # in more advanced sleep modes, sleep microprocessor undil D0 pressed (note: D0 is active low unlike D1,D2)
                    if sleep_mode == 2:
                        button_D0.deinit()
                        pin_alarm = alarm.pin.PinAlarm(pin=board.D0, value=False, pull=True)
                        alarm.light_sleep_until_alarms(pin_alarm)  # light microprocessor sleep
                        # reinitialize button to its original function after wakeup
                        button_D0 = digitalio.DigitalInOut(board.D0)
                        button_D0.switch_to_input(pull=digitalio.Pull.UP)
                    if sleep_mode == 3:
                        deep_sleep()
                        # will never reach this line: system reboots when exiting deep sleep
                elif (time.monotonic() - last_button_time) > INACTIVITY_DIM_TIME:
                    # dimming display: likely doesn't save much power, but cues user display is about to sleep
                    display.brightness = TFT_DIM_BRIGHTNESS
        if button_pressed(1) and not debounce_D1:
            clear_die_display()
            debounce_D1 = True
            # Change which die to roll, can do even during an existing roll animation (restart timer)
            dice_index = (dice_index + 1) % len(dice_types)
            current_die = dice_types[dice_index]
            text_D1[0].text = f"< D{current_die['sides']}  "
            # update background polygon
            polygon_rotation = current_die["poly_r0"]
            polygon.points = generate_polygon_pts(current_die["polygon_sides"], rotation=polygon_rotation)
            last_button_time = time.monotonic()
            animation_running = True
            animation_ticks = 0
            animation_t0 = time.monotonic()
        debounce_buttons()
    time.sleep(0.01)
