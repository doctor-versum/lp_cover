import launchpad_py as launchpad
import time
import random

lp = launchpad.LaunchpadMiniMk3()

lp.Open()
lp.Reset()

# Set all LEDs to magenta
for i in range(9):
    for j in range(9):
        lp.LedCtrlXY(i, j, 64, 0, 64)  # Magenta

# Optional: Set the center LED to purple initially (as in the original excerpt)
lp.LedCtrlXY(4, 4, 64, 0, 32)

lp.Close()