# To use, rename this to boot.py and copy to device
# If this boot.py is present and D# is pressed on boot, enable writing of filesystem by program (but not by computer)
# To pair with test_log_power_usage.py

import time
import board
import digitalio
import storage
import neopixel
import alarm

CUSTOM_BOOT = True # set to True to run this boot routine

if CUSTOM_BOOT:

  button = digitalio.DigitalInOut(board.D2)
  button.switch_to_input(pull=digitalio.Pull.DOWN)

  pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
  pixel.brightness = 0.3

  # if we're waking after an alarm (rebooting after deep sleep), automatically set the system in write mode, unless D2 pressed!
  if alarm.wake_alarm and not button.value:
    storage.remount("/", readonly=False)
    print("Mounting filesystem as readable to program after wake (from deep sleep, presumably)")
  #  pixel.fill((0,255,0))
    time.sleep(0.2)
    pixel.fill((0,0,0))
  else:
    # Turn on neopixel to indicate when to press button
    pixel.fill((255,255,255))
    time.sleep(1)
    pixel.fill((0,0,0))
    # If D2 is pressed, set filesystem writable by CircuitPython and glow neopixel green (vs. red) to confirm
    if button.value:
      storage.remount("/", readonly=False)
      print("Mounting filesystem as readable to program")
      pixel.fill((0,255,0))
      time.sleep(1)
      pixel.fill((0,0,0))
    else:
      storage.remount("/", readonly=True)
      print("D0 not pressed at boot: filesystem left as read-only")
      pixel.fill((255,0,0))
      time.sleep(1)
      pixel.fill((0,0,0))

