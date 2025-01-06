import board
import displayio
import terminalio
# For imports below here, need to copy the libraries from the circuitpython bundle to the local lib/ folder
from adafruit_display_text import label

# Test drawing some graphics and text to a TFT display, based on overview at
#  https://learn.adafruit.com/using-circuitpython-displayio-with-a-tft-featherwing/2-4-tft-featherwing

print("running test_display.py")

# board-specific initialization (for this S3 TFT Feather)
display = board.DISPLAY

# Next we create an image group we can add elements to, and add that group to the display
# The display will now automatically handle updating the screen with all objects in this group
display_group = displayio.Group()
display.root_group = display_group

print(f"display: {display.width}x{display.height} px")

# Next we create a Bitmap which is like a canvas that we can draw on.
# We create a Palette with one color and set that color to 0x00FF00 which happens to be green.
canvas = displayio.Bitmap(display.width, display.height, 1)
color_palette = displayio.Palette(1)
color_palette[0] = 0x00FF00 # Bright Green

# With all those pieces in place, we create a TileGrid by passing the bitmap and palette and draw it at (0, 0) which represents the display's upper left.
background = displayio.TileGrid(canvas, pixel_shader=color_palette, x=0, y=0)
display_group.append(background)

# Now draw a smaller box
border = 20
inner_bitmap = displayio.Bitmap(display.width - 2 * border, display.height - 2 * border, 1)
inner_palette = displayio.Palette(1)
inner_palette[0] = 0xAA0088 # Purple
inner_sprite = displayio.TileGrid(inner_bitmap,
                                  pixel_shader=inner_palette,
                                  x=border, y=border)
display_group.append(inner_sprite)

# Add some scaled text
text_group = displayio.Group(scale=2, x=border * 2, y = border * 2)
text = f"Hello World!\n{display.width}x{display.height} pixels"
text_area = label.Label(terminalio.FONT, text=text, color=0xFFFF00)
text_group.append(text_area)
display_group.append(text_group)

while True:
    pass
