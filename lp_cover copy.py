import launchpad_py as launchpad
import time
import random
import threading
import sys
import importlib

import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

lp = launchpad.LaunchpadMiniMk3()
paused = False
running = True
connected = False  # Neuer Statusflag für die Launchpad-Verbindung

def connect_launchpad():
    global connected, lp
    while True:
        if not paused:
            try:
                lp = None  # Set lp to None to ensure a fresh connection attempt
                # Ein neuer lp-Handle wird erzeugt.
                lp = launchpad.LaunchpadMiniMk3()
                print("lp: ", lp)
                lp.Open()
                lp.Reset()
                connected = True
                print("Launchpad connected.")
                return
            except Exception as e:
                print(f"Error connecting to Launchpad: {e}")
                time.sleep(10)  # Wait before retrying
        else:
            print("Launchpad connection paused.")
            time.sleep(5)

def disconnect_launchpad():
    global connected
    if connected:
        lp.Reset()
        lp.Close()
        connected = False
        print("Launchpad disconnected.")
        threading.Thread(target=connect_launchpad, daemon=True).start()  # Reconnect if paused

def main():
    # Define color codes
    MAGENTA = (64, 0, 64)
    color_options = [
        (32, 0, 64),
        (16, 0, 64),
        (64, 0, 32)
    ]

    # Initialize all LEDs to magenta and track their current colors
    current_colors = {}
    for i in range(9):
        for j in range(9):
            lp.LedCtrlXY(i, j, *MAGENTA)  # Magenta
            current_colors[(i, j)] = MAGENTA

    # Dictionary to track when a LED was changed to a non-magenta color
    non_magenta_fields = {}  # key: (x, y), value: timestamp
    print("Started animation. Use das Tray-Menü zum Pausieren & Schließen.")

    try:
        while running:
            if not paused and connected:
                current_time = time.time()
                # Revert any fields that have been non-magenta for 10 seconds
                for (x, y), changed_time in list(non_magenta_fields.items()):
                    if current_time - changed_time >= 10:
                        lp.LedCtrlXY(x, y, *MAGENTA)  # Revert back to Magenta
                        current_colors[(x, y)] = MAGENTA
                        del non_magenta_fields[(x, y)]

                # Pick a random LED coordinate and a random color from the list
                x = random.randint(0, 8)
                y = random.randint(0, 8)
                new_color = random.choice(color_options)
                
                # If the LED already has the chosen color, choose another LED immediately
                if current_colors[(x, y)] == new_color:
                    continue
                else:
                    lp.LedCtrlXY(x, y, *new_color)  # Set to the new color
                    current_colors[(x, y)] = new_color
                    non_magenta_fields[(x, y)] = current_time
                    print(f"Changed LED at ({x}, {y}) to {new_color}")
                    
                    # Wait a short random time to speed up the color changes
                    time.sleep(random.uniform(0.05, 0.2))
            else:
                # Weder versuchen wir, LEDs zu verändern; sondern kurz warten.
                time.sleep(0.2)
    except KeyboardInterrupt:
        cleanup()

def cleanup():
    print("Exiting...")
    lp.Reset()
    lp.Close()
    sys.exit(0)

def create_image():
    # Erstelle ein simples Icon-Bild (64x64) mit einem magentafarbenen Kreis.
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), "white")
    dc = ImageDraw.Draw(image)
    dc.ellipse((8, 8, width-8, height-8), fill="magenta")
    return image

def toggle_pause(icon, item):
    global paused
    paused = not paused
    if paused:
        print("Paused.")
        disconnect_launchpad()  # Trenne einmalig die Verbindung.
    else:
        print("Unpaused.")
        # Starte connect_launchpad in einem separaten Thread, damit das Tray-Icon reaktionsfähig bleibt.
        threading.Thread(target=connect_launchpad, daemon=True).start()

def exit_program(icon, item):
    # Gleicher Ablauf wie bei KeyboardInterrupt
    icon.stop()
    cleanup()

if __name__ == '__main__':
    connect_launchpad()
    main_thread = threading.Thread(target=main, daemon=True)
    main_thread.start()

    # Erstelle das Tray-Symbol mit Menüeinträgen
    menu = (item('Pause/Unpause', toggle_pause), item('Close', exit_program))
    tray_icon = pystray.Icon("lp_cover", create_image(), "LP Cover", menu)
    tray_icon.run()