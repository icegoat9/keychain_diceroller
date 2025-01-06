# Test drawing (and maybe rotating) polygons with a few different existing libraries to compare speed, etc
# Note: vectorio method seemed the fastest so will likely start with that
import board
import displayio
import terminalio
import math
import time
import digitalio
import vectorio

# For imports below here, need to copy the relevant libraries from the circuitpython bundle to the local lib/ folder
from adafruit_display_text import label
from adafruit_display_shapes.polygon import Polygon

TFT_BRIGHTNESS = 0.5

# Disable Neopixel to save power
neopixel_power = digitalio.DigitalInOut(board.NEOPIXEL_POWER)
neopixel_power.direction = digitalio.Direction.OUTPUT
neopixel_power.value = False

polygon_types = [3, 4, 5, 6, 10, 12, 20]
polygon_index = 3  # 6-sided
polygon_sides = polygon_types[polygon_index]

# only partially implemented
polymode = 0  # 0 = filled vectorio polygon , 1 = hollow via dual vectorio polygon,
# TODO (not implemented): 2 = drawn by scratch from lines, 3 = combo of 0 and 2, 4 = hollow via adafruit_display_shapes.polygon

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


def any_button_pressed():
    return button_pressed(0) or button_pressed(1) or button_pressed(2)


# board-specific display initialization (for this S3 TFT Feather)
display = board.DISPLAY
display.brightness = TFT_BRIGHTNESS

# Create image group to add elements to, and add that group to the display
# The display will now automatically handle updating the screen with all objects in this group
display_group = displayio.Group()
display.root_group = display_group

canvas = displayio.Bitmap(display.width, display.height, 1)
background_palette = displayio.Palette(1)
background_palette[0] = 0x000000
background = displayio.TileGrid(canvas, pixel_shader=background_palette, x=0, y=0)
display_group.append(background)

DIEROLL_X0 = display.width - display.height

# Menu text 
text_D1 = displayio.Group(scale=2, x=0, y=display.height // 2)
text = f"{polygon_types[polygon_index]}"
text_area = label.Label(terminalio.FONT, text=text, color=0xFFFFFF)
text_D1.append(text_area)
display_group.append(text_D1)

text_D2 = displayio.Group(scale=2, x=0, y=display.height - 10)
text = f"mode{polymode}"
text_area = label.Label(terminalio.FONT, text=text, color=0xFFFFFF)
text_D2.append(text_area)
display_group.append(text_D2)

def calculate_polygon_pts(n, rotation = 0, scale = 1.0, x_offset = 0, y_offset = 0):
    # TODO: speed up by not re-calculating everything each time called unless needed
    sidelen = math.pi * display.height / (1.2 * n)   # approximation
    radius = 0.9 * scale * (display.height / 2)
    angle_increment = 360 / n
    # let's have angles read clockwise from the +X axis
    pts = []
    for i in range(n):
        an = math.radians(rotation + angle_increment * i)
        x = radius * math.cos(an)
        y = radius * math.sin(an)
        pts.append((int(round(x + x_offset)), int(round(y + y_offset))))
    return pts

# Polygon object
poly_palette = displayio.Palette(1)
poly_palette[0] = 0x00FFFF
poly_points = calculate_polygon_pts(6)
polygon = vectorio.Polygon(pixel_shader=poly_palette, points=poly_points, x=DIEROLL_X0 + display.height // 2, y=display.height // 2)
display_group.append(polygon)

# Black polygon object (only used if we want to stack this and the above to make a polygon outline)
poly2_palette = displayio.Palette(1)
poly2_palette[0] = 0x707070
poly2_points = calculate_polygon_pts(6, 0, 0.95)
#polygon_black = vectorio.Polygon(pixel_shader=poly2_palette, points=poly2_points, x=DIEROLL_X0 + display.height // 2, y=display.height // 2)
polygon_black = vectorio.Polygon(pixel_shader=poly2_palette, points=[(0,0),(0,0),(0,0)], x=DIEROLL_X0 + display.height // 2, y=display.height // 2)
display_group.append(polygon_black)

# alternate polygon
poly3_points = calculate_polygon_pts(6, rotation=0, scale = 0.9, x_offset = 90, y_offset = 70)
polygon_3 = Polygon(poly3_points, outline = 0x0000FF, colors = 1)
display_group.append(polygon_3)

# Polygon # text
text_poly = displayio.Group(scale=4, x=DIEROLL_X0 + display.height // 2 - 10, y=display.height // 2)
text_area = label.Label(terminalio.FONT, text=f"{polygon_types[polygon_index]}", color=0x000000)
text_poly.append(text_area)
display_group.append(text_poly)

rotation = 0

while True:
    if button_pressed(1):
        polygon_index = (polygon_index + 1) % len(polygon_types)
        polygon_sides = polygon_types[polygon_index]
        text_D1[0].text = str(polygon_sides)
        text_poly[0].text = str(polygon_sides)
        # text_poly[0].x = DIEROLL_X0 + display.height // 2 + 10 - 20 * len(str(polygon_types[polygon_index]))
        while button_pressed(1):
            pass  # wait until button is released
    if button_pressed(2):
        polymode = (polymode + 1) % 4
        text_D2[0].text = f"mode{polymode}"
        if polymode != 1:
            polygon_black.points = [(0,0),(0,0),(0,0)]
        while button_pressed(2):
            pass  # wait until button is released
    if polymode == 0 or polymode == 1 or polymode == 3:
        polygon.points = calculate_polygon_pts(polygon_sides, rotation)
    if polymode == 1:
        polygon_black.points = calculate_polygon_pts(polygon_sides, rotation, 0.95)
    if polymode == 2 or polymode == 3:
        # hack assuming this polygon is second to last in list
        poly3_points = calculate_polygon_pts(polygon_sides, rotation, scale = 0.9, x_offset = 90, y_offset = 70)
        polygon_3 = Polygon(poly3_points, outline = 0x0000FF, colors = 1)
        display_group[-2] = polygon_3
    rotation += 5
    time.sleep(0.01)