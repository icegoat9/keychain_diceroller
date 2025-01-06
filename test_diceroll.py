# Scratchpad / tests for a die roll based on input button, drawing graphics, etc

# Major work moved to diceroll.py

import board
import displayio
import terminalio
import random
#import time
import digitalio

# For imports below here, need to copy the libraries from the circuitpython bundle to the local lib/ folder
from adafruit_display_text import label

# Configure three input buttons
button_D0 = digitalio.DigitalInOut(board.D0)
button_D0.switch_to_input(pull=digitalio.Pull.UP)
button_D1 = digitalio.DigitalInOut(board.D1)
button_D1.switch_to_input(pull=digitalio.Pull.DOWN)
button_D2 = digitalio.DigitalInOut(board.D2)
button_D2.switch_to_input(pull=digitalio.Pull.DOWN)


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


# board-specific initialization (for this S3 TFT Feather)
display = board.DISPLAY

# Next we create an image group we can add elements to, and add that group to the display
# The display will now automatically handle updating the screen with all objects in this group
display_group = displayio.Group()
display.root_group = display_group

# Next we create a Bitmap which is like a canvas that we can draw on.
# We create a Palette with one color and set that color to 0x00FF00 which happens to be green.
canvas = displayio.Bitmap(display.width, display.height, 1)
color_palette = displayio.Palette(1)
color_palette[0] = 0x696969   # Gray

# With all those pieces in place, we create a TileGrid by passing the bitmap and palette and draw it at (0, 0) which represents the display's upper left.
background = displayio.TileGrid(canvas, pixel_shader=color_palette, x=0, y=0)
display_group.append(background)

# Now draw a smaller box on the right (135x135 w/ tbd border)
border = 10
inner_bitmap = displayio.Bitmap(135 - 2 * border, 135 - 2 * border, 1)
inner_palette = displayio.Palette(1)
inner_palette[0] = 0xD2B48C   # Tan
inner_sprite = displayio.TileGrid(inner_bitmap, pixel_shader=inner_palette, x=240 - 135 + border, y=border)
display_group.append(inner_sprite)

# Menu block and text
black_bitmap = displayio.Bitmap(240 - 135, 135, 1)
black_palette = displayio.Palette(1)
black_palette[0] = 0x000000
black_sprite = displayio.TileGrid(black_bitmap, pixel_shader=black_palette, x=0, y=0)
display_group.append(black_sprite)


text_D0 = displayio.Group(scale=2, x=0, y=10)
text = "< CFG"
text_area = label.Label(terminalio.FONT, text=text, color=0xFFFFFF)
text_D0.append(text_area)
display_group.append(text_D0)

text_D1 = displayio.Group(scale=2, x=0, y=135 // 2)
text = "< DIE"
text_area = label.Label(terminalio.FONT, text=text, color=0xFFFFFF)
text_D1.append(text_area)
display_group.append(text_D1)

text_D2 = displayio.Group(scale=2, x=0, y=125)
text = "< ROLL"
text_area = label.Label(terminalio.FONT, text=text, color=0xFFFFFF)
text_D2.append(text_area)
display_group.append(text_D2)


# placeholder for dice text

text_roll = displayio.Group(scale=8, x=240 - (135 // 2) - 15, y=135 // 2)
text = ""
text_area = label.Label(terminalio.FONT, text=text, color=0x303030)
text_roll.append(text_area)
display_group.append(text_roll)

dice_types = [
    {"sides": 3, "zero_index": False, "symbol_list": ["-", "O", "+"]},
    {"sides": 6, "zero_index": False},
    {"sides": 10, "zero_index": True},
    {"sides": 20, "zero_index": False},
    {"sides": 100, "zero_index": True},
]

dice_index = 3  # D20
text_D1[0].text = f"< D{dice_types[dice_index]['sides']}"

def rolldie():
    """Roll the die type specified by dice_index, return result (number or string)."""
    die = dice_types[dice_index]
    n = random.randint(1, die["sides"])
    if die["zero_index"] or 'symbol_list' in die:
        n -= 1
    if 'symbol_list' in die:
        return die["symbol_list"][n]
    return n

D1_debounced = True

while True:
    if D1_debounced and button_pressed(1):
        dice_index = (dice_index + 1) % len(dice_types)
        text_D1[0].text = f"< D{dice_types[dice_index]['sides']}"
        D1_debounced = False
    if not D1_debounced and not button_pressed(1):
        D1_debounced = True
    if button_pressed(2):
        roll = str(rolldie())
        text_roll.x = 240 - 54 - 32 * len(roll)
        text_roll[0].text = roll
