import board
import displayio
import terminalio

# For imports below here, need to copy the libraries from the circuitpython bundle to the local lib/ folder
from adafruit_display_text.label import Label
from adafruit_display_shapes.rect import Rect

print("running test_display_location.py...\n (check centering, may vary device to device based on assembly)")

display = board.DISPLAY
display_group = displayio.Group()
display.root_group = display_group

print(f"display: {display.width}x{display.height} px")

# Blank background
background = displayio.Bitmap(display.width, display.height, 1)
background_palette = displayio.Palette(1)
background_palette[0] = 0x000000
display_group.append(displayio.TileGrid(background, pixel_shader=background_palette, x=0, y=0))

# Now draw nested boxes
colorlist = (0x00FF00, 0xFF7777)
for i in range(5):
    c = colorlist[i % len(colorlist)]
    display_group.append(
        Rect(
            x=i * 2,
            y=i * 2,
            width=display.width - i * 4,
            height=display.height - i * 4,
            fill=None,
            outline=c,
            stroke=1,
        )
    )

# Add some centered text
text = f"Test Display\nCentering\n{display.width}x{display.height} pixels"
text_area = Label(terminalio.FONT, text=text, color=0xFFFFFF)
text_scale = 2
text_area.anchor_point = (0.5, 0.5)
text_area.anchored_position = (display.width // (text_scale * 2), display.height // (text_scale * 2))
text_group = displayio.Group(scale=text_scale, x=0, y=0)
text_group.append(text_area)
display_group.append(text_group)

while True:
    pass
