## diceroll_feather: Quick TODO list
```
[x] Core dice rolling and graphics proof of concept (test_diceroll.py)
[x] Read battery level and display (where?)
    Save power by...
[x]   Turning off display after N seconds
[x]   Going into actual processor sleep mode?
[x]   Sleep Memory for Deep Sleep
[x]   Debug deep sleep crash / restart on actual battery power (pullup issue, perhaps? happens w/ pullup set true or false)
[x]     Test using D0 (active low) as interrupt / wake pin instead in case this is something pullup related
[x]   **Create much simpler test case that just prints battery % to screen in larger font, and after waking from sleep
        also calculates "% drop in XX seconds since last button press" (e.g. 'press D1 to change sleep mode, D2 to initiative sleep, D0 to wake')
[x]   Test power draw in light sleep mode with D0 as wake pin (not sure why it would be different, just in case we're not fully sleeping?)
[ ]   Post on forums to ask about current draw seen in light sleep or with TFT off (once test case program implemented)
[x]   Rerun deep sleep logging test but with a pin alarm as well (since with pin alarm on, sleep draws more power than timer deep sleep per [this link](https://learn.adafruit.com/deep-sleep-with-circuitpython/power-consumption#esp32-s2-timealarm-light-sleep-sample-power-consumption-3079939))
[x]   Change backlight brightness on board for dim mode instead of changing colors
[x]   If the D0 deep wake works, swap UI so D0 rolls die?
[x]   Two-stage sleep: light sleep earlier, then deep sleep only after a few minutes? (do math on mA draw and life)
[x]     auto-roll die after waking from deep sleep!
[x]     or instead, save last_roll in sleep memory and display that (if last_roll: ...)
[x] Larger battery % font, no voltage
[x] Add battery icon (w/ red, yellow, green)
[x] Measure energy draw in various sleep modes...
[x] Maybe: debounce D2 (only trigger once on press) and instead 'animate' roll by cycling through values for some amount of time
           rather than depending on how long the user presses the button
[x] Add more animation of the roll? (N-sided dice polygon rotating, for example, especially if rotation is a primitive we have)
[x] Different polygon around die area based on D# (triangle for D3, square for D6, facet for D10/D20, etc) -- needs some thought
[x]   Should we erase the previously-rolled # (or change to ?) in that case so not confusing to see large D20 value in a D6?
[x] Select smaller battery
[x] Design simple case and order
[x] Test desoldering battery connector and replace with straight connector, and desoldering Stemma connector
[ ] Debug occasional graphical glitch with switching die: previous polygon not erased? (may be fixed now)
```
## Lower priority TODO
```
Software Features:
[ ] Figure out if it's possible to make the CircuitPython 'boot-up' less verbose (e.g. don't show on-screen boot text)
[ ] Add ability to roll '2D6' as an option
[ ]   (or another button to cycle through # to roll...? reset to 1 if first time used in a while? save to memory?)

Hardware Features:
[ ] Maybe: revise case to have USB C fit into surrounded slot not just cutout (need space for LEDs/resistors adjacent)
[x] Thicker top-plate that also hides edges of display
[x]   Separate (colorful) plastic button caps on each button (captured by this thicker top plate)
[x]   New rear-mount case design (with threads or inserts in rear of thicker top plate)
[ ] Look into availability of heat-set M2.5 and M2 threaded inserts / helicoils

Cleanup and test
[x] Refactor dieroll()
[ ] Precompute polygon vertices for animation, test to see if that speeds animation
    (either on dice type switch, or precompute all possible rotations in a big lookup table)
    (WIP: ran a few tests but not using, good enough for now)
[ ] Determine if initial black bitmap needed
[ ] Clean up palette assignment to objects (sometimes use three lines, not needed)
[ ] More variable renames e.g. gfx_ or obj_ or gfx_layer_, see notes in code
[x] Remove, comment out, or hide behind a "allow_sleepmode_change" global the unused sleep modes 
[ ] External power meter logging of current draw of each peripheral and sleep mode:
[ ]   Neopixel, I2C/TFT, backlight brightness, time.sleep duration, light/deep sleep, Wifi/bluetooth, etc
[ ] Remove TODOs from code
```


## Scratchpad / Notes

