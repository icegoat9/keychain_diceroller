# Test board life with print, LED, neopixel
print("Hello New World!")

import board
import digitalio
import time
import neopixel

led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
pixel.brightness = 0.3

cycle = 1

while True:
    pixel.fill((255, 0, 0))
    led.value = True
    time.sleep(0.1)
    led.value = False
    time.sleep(0.5)
    pixel.fill((0, 255, 0))
    led.value = True
    time.sleep(0.1)
    led.value = False
    time.sleep(0.5)
    pixel.fill((0, 0, 255))
    led.value = True
    time.sleep(0.1)
    led.value = False
    time.sleep(0.5)
    print(f"Hello loop {cycle}")
    cycle += 1
