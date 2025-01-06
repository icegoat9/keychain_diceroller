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

# does importing WiFi let us shut it off? (didn't make an obvious battery difference, though...)
# import wifi
# wifi.radio.enabled = False

TFT_BRIGHTNESS = 0.5
TFT_DIM_BRIGHTNESS = 0.1
INACTIVITY_DIM_TIME = 10
INACTIVITY_SLEEP_TIME = 15
INACTIVITY_DEEPSLEEP_TIME = 180  # the main power saving measure...

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

polygon_rotation = 0  # 0 to 360...
animation_running = False  # is a die roll currently animating?
ANIMATION_DURATION = 0.5

# if we just woke up from a deep sleep and reboot, load some config values from backup RAM / sleep memory
if alarm.wake_alarm:
    dice_index = alarm.sleep_memory[0]

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

## Button management and debouncing

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


def debounce_buttons():
    global debounce_D1
    if not button_pressed(1):
        debounce_D1 = False
    global debounce_D2
    if not button_pressed(2):
        debounce_D2 = False

debounce_D1 = False
debounce_D2 = False


############ WIP polygon rotation speed improvement idea (not yet used)
#   initial polygon configuration to minimize computation needed in the generate_polygon_pts() call below
#   TBD if this speeds it (is this math bottleneck or display interface?)
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
############### end WIP code

def generate_polygon_pts(n, rotation=0, scale=None, x_offset=0, y_offset=0):
    """Calculate vertices of polygon with N sides."""
    # TODO: perhaps don't re-calculate all of these every time called if that slows us down
    #       (can pre-calculate some only when we change die type to roll?)
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

##################
## Display Layout

# Create an image group we can add elements to, and add that group to the display
# The display will now automatically handle updating the screen with all objects in this group
display_group = displayio.Group()
display.root_group = display_group

# Next we create a Bitmap which is like a canvas that we can draw on.
canvas = displayio.Bitmap(display.width, display.height, 1)
# TODO: rename all these with some common prefix such as obj_ or layer_ or gfx_, to make later editing of these globals more clear?
# We create a Palette with one color and set that color to a value
background_palette = displayio.Palette(1)
background_palette[0] = 0x000000  # Black
# With all those pieces in place, we create a TileGrid by passing the bitmap and palette and draw it at (0, 0) which represents the display's upper left.
background = displayio.TileGrid(canvas, pixel_shader=background_palette, x=0, y=0)
display_group.append(background)

# Now draw the die icon background (filled polygon) on the right
DIEROLL_X0 = display.width - display.height
poly_palette = displayio.Palette(1)
poly_palette[0] = 0xCF50FA  # purple
current_die = dice_types[dice_index]
poly_points = generate_polygon_pts(current_die["polygon_sides"], rotation=current_die["poly_r0"])
polygon = vectorio.Polygon(
    pixel_shader=poly_palette, points=poly_points, x=DIEROLL_X0 + display.height // 2, y=display.height // 2
)
display_group.append(polygon)

# initial die value (and do a first roll on startup or resume from deep sleep)
DIE_TEXT_SCALE = 6
text_roll_color = 0x000000
text_roll_area = label.Label(terminalio.FONT, text="??", color=text_roll_color)
text_width = text_roll_area.bounding_box[2] * DIE_TEXT_SCALE
text_roll = displayio.Group(
    scale=DIE_TEXT_SCALE, x=DIEROLL_X0 + display.height // 2 - text_width // 2 + 6, y=display.height // 2
)
text_roll.append(text_roll_area)
display_group.append(text_roll)

def roll_die_and_update_display():
    text_roll[0].text = rolldie(dice_types[dice_index])
    # note: bounding_box = (x, y, width, height)
    text_width = text_roll_area.bounding_box[2] * DIE_TEXT_SCALE
    text_roll.x = DIEROLL_X0 + display.height // 2 - text_width // 2

def clear_die_display():
    text_roll[0].text = ""

roll_die_and_update_display()

## Menu text by buttons

text_D0 = displayio.Group(scale=2, x=0, y=10)
text = "< ROLL"
text_area = label.Label(terminalio.FONT, text=text, color=0xFFFFFF)
text_D0.append(text_area)
display_group.append(text_D0)

text_D1 = displayio.Group(scale=2, x=0, y=display.height // 2)
text_placeholder = "< D?"
text_area = label.Label(terminalio.FONT, text=text_placeholder, color=0xFFFFFF)
text_D1.append(text_area)

# Update D1 text with current die value
def set_display_die_info():
    text_D1[0].text = f"< D{dice_types[dice_index]['sides']}"

set_display_die_info()
display_group.append(text_D1)

## Battery % reading and display

def get_battery():
    """Return battery %, clamped from 0 to 100"""
    return max(0, min(100, monitor.cell_percent))

def get_battery_color(pct):
    if pct <= 20:
        return 0xFF0000  # red
    elif pct <= 70:
        return 0xFFFF00  # yellow
    else:
        return 0x00FF00  # green

# Battery visual icon
bat_icon = displayio.Group()
bat_icon_palette = displayio.Palette(1)

# get battery info
bat_level = get_battery()  # - random.randint(0,100)  # temporary random # for testing range of values
bat_color = get_battery_color(bat_level)

# Draw frame of battery as filled polygon
BXY = 3   # battery offset from display edge
BH = 15  # battery icon height
BW = 35  # battery icon width
BS = BH // 3  # battery step
BG = 2  # battery gap
BAT_THRESH_HIDE = 70
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
    x=BXY,
    y=display.height - BH - BXY,
)

# now clear out part of the battery w/ a black rectangle
black_palette = displayio.Palette(1)
black_palette[0] = 0x000000
fill_width = max(1, int((BW - BS - 2 * BG) * (100 - bat_level) / 100))
bat_icon_filling = vectorio.Rectangle(
    pixel_shader=black_palette,
    width=fill_width,
    height=BH - 2 * BG,
    x=BW - BS - BG - fill_width + BXY,
    y=display.height - BH + BG - BXY,
)

bat_icon.append(bat_icon_frame)
bat_icon.append(bat_icon_filling)

def update_battery_icon(bat_level = None):
    # update length and color of battery icon based on actually battery level
    # if a battery level was not passed to this function (e.g. for debugging), read it directly
    # TODO: remove some redundant layout code above since we call this function
    if not bat_level:
        bat_level = get_battery()
    # hide icon if battery nearly full
    bat_icon.hidden = (bat_level >= BAT_THRESH_HIDE)
    # update palette used for existing battery icon
    bat_icon_palette[0] = get_battery_color(bat_level)
    # update size and location of '% battery drained' black bar
    fill_width = max(1, int((BW - BS - 2 * BG) * (100 - bat_level) / 100))
    bat_icon_filling.width = fill_width
    bat_icon_filling.x = BW - BS - BG - fill_width + BXY

update_battery_icon()
display_group.append(bat_icon)

## Power management and sleep functionality

def enter_low_power():
    # Turn off display to save a bit of power
    global low_power_mode
    low_power_mode = True
    tft_i2c_power.value = False


def exit_low_power():
    global low_power_mode
    low_power_mode = False
    tft_i2c_power.value = True
    display.brightness = TFT_BRIGHTNESS

# handle dimming and sleeping after periods of inactivity
last_button_time = time.monotonic()

def time_since_last_button():
    return time.monotonic() - last_button_time

def deep_sleep():
    # save a few key status values to backup RAM ('sleep memory') to reload after deep sleep reboot
    alarm.sleep_memory[0] = dice_index
    button_D0.deinit()
    pin_alarm = alarm.pin.PinAlarm(pin=board.D0, value=False, pull=True)
    alarm.exit_and_deep_sleep_until_alarms(pin_alarm)
    # will never reach this point: reboots after exiting deep sleep

### Animation dieroll globals

def start_dieroll():
    global animation_running
    global animation_ticks
    global animation_t0
    animation_running = True
    animation_ticks = 0
    animation_t0 = time.monotonic()

### Roll the die on startup

start_dieroll()


# main program loop
while True:
    # D2 = reserve for future use (TODO? change number of dice to roll)
    if button_pressed(2):
#        update_battery_icon(random.randint(0,100))   # debug for testing
#        while button_pressed(2):
#            pass
        pass
    #### Low Power Mode: just check for wakes or need to deep sleep
    if low_power_mode:
        if time_since_last_button() > INACTIVITY_DEEPSLEEP_TIME:
            deep_sleep()
            raise RuntimeError("Unreachable code: deep sleep should have rebooted on wake.")
        if any_button_pressed():
            exit_low_power()
            while button_pressed(1) or button_pressed(2):
                pass  # wait until D1 or D2 released, but D0 will trigger a new roll, below
            last_button_time = time.monotonic()  # reset sleep timer once no longer pressing a button
    else:
        ### Standard Main Loop, if not in low power mode:
        if animation_running:
            # While animating a die roll, skip most other main loop code for speed, though can still check for changing dice
            polygon_rotation = (polygon_rotation + 10) % 360
            polygon.points = generate_polygon_pts(dice_types[dice_index]["polygon_sides"], rotation=polygon_rotation)
            # only update number every N animation cycles
            if (animation_ticks % 2) == 0:
                roll_die_and_update_display()
            animation_ticks += 1
            if time.monotonic() - animation_t0 > ANIMATION_DURATION:
                animation_running = False
                while button_pressed(0):
                    pass  # wait until D0 released if not already
        else: # Animation Not Running
            if any_button_pressed():
                display.brightness = TFT_BRIGHTNESS
                last_button_time = time.monotonic()
            if button_pressed(0):
                start_dieroll()
            # Read battery value and update icon
            update_battery_icon()
            # If no button has been pressed in a while, turn off display and I2C to save battery
            if time_since_last_button() > INACTIVITY_SLEEP_TIME:
                enter_low_power()
            elif time_since_last_button() > INACTIVITY_DIM_TIME:
                # dimming display: likely doesn't save much power, but cues user display is about to sleep
                display.brightness = TFT_DIM_BRIGHTNESS
        # Change which die to roll:
        #  Can even do this during an ongoing roll automation (restarts animation timer)
        if button_pressed(1) and not debounce_D1:
            clear_die_display()
            debounce_D1 = True
            dice_index = (dice_index + 1) % len(dice_types)
            current_die = dice_types[dice_index]
            set_display_die_info()  # updates text label based on global current_die
            # update background polygon
            polygon_rotation = current_die["poly_r0"]
            polygon.points = generate_polygon_pts(current_die["polygon_sides"], rotation=polygon_rotation)
            last_button_time = time.monotonic()
            start_dieroll()
        debounce_buttons()
    time.sleep(0.01)
