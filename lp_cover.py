import time
import random
import threading
import sys
import launchpad_py as launchpad
import soundcard as sc
import numpy as np
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

# Globale Flags
paused = False
running = True
connected = False
active_mode = "audio"  # "audio" oder "fallback"
last_audio_detection = time.time()  # wird vom Audio-Thread aktualisiert
lp = None  # Launchpad-Handle

DEFAULT_COLOR_1 = (64, 0, 64)
DEFAULT_COLOR_2 = (0, 64, 64)

COLOR_PALETTE = [
    DEFAULT_COLOR_1,
    DEFAULT_COLOR_2,
    (32, 0, 64),
    (16, 0, 64),
    (64, 0, 32),
    (0, 48, 64),   # Hellblauer Ton A
    (0, 64, 48)    # Hellblauer Ton B
]

###############################################
# Launchpad-Verbindung
###############################################
def connect_launchpad():
    global connected, lp, paused
    while True:
        if not paused:
            try:
                candidate = launchpad.LaunchpadMiniMk3()
                candidate.Open()
                candidate.Reset()
                lp = candidate
                connected = True
                print("Launchpad connected. Handle:", lp)
                return
            except Exception as e:
                lp = None
                connected = False
                print(f"Error connecting to Launchpad: {e}")
                time.sleep(10)
        else:
            print("Launchpad connection paused.")
            time.sleep(5)

def disconnect_launchpad():
    global connected, lp
    if connected and lp is not None:
        try:
            lp.Reset()
            lp.Close()
        except Exception as e:
            print("Fehler beim Disconnect:", e)
        connected = False
        print("Launchpad disconnected.")
        threading.Thread(target=connect_launchpad, daemon=True).start()

###############################################
# Funktion: Muster bei Spike anzeigen
###############################################
def set_peak_pattern():
    # Definiere einige Magenta-/Lilatöne
    peak_colors = COLOR_PALETTE
    if connected and lp is not None:
        for x in range(9):
            for y in range(9):
                color = random.choice(peak_colors)
                try:
                    lp.LedCtrlXY(x, y, *color)
                except Exception as e:
                    print("Error updating LED for peak pattern:", e)

###############################################
# Audioanalyse-Thread
###############################################
def audio_analysis_loop():
    global active_mode, last_audio_detection, lp, running, connected
    sample_rate = 48000
    chunk_size = 1024           # Anzahl der Frames pro Chunk
    threshold = 0.40            # Initialer Schwellenwert für Spike-Erkennung
    f_min = 400
    f_max = 1000

    mic = sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True)
    with mic.recorder(samplerate=sample_rate) as recorder:
        print("Starte Live-Audioanalyse. Drücke Strg+C zum Beenden.")
        last_detection_time = time.time()
        while running:
            current_time = time.time()
            data = recorder.record(numframes=chunk_size)
            # Analyse des ersten Kanals
            channel_data = data[:, 0]
            # FFT durchführen
            fft_data = np.fft.rfft(channel_data)
            freqs = np.fft.rfftfreq(len(channel_data), d=1/sample_rate)
            # Nur den gewünschten Frequenzbereich betrachten
            band_mask = (freqs >= f_min) & (freqs <= f_max)
            magnitudes = np.abs(fft_data[band_mask]) / chunk_size
            peak = (magnitudes.max() if magnitudes.size > 0 else 0) * 5

            if peak > threshold:
                print(f"Spike erkannt: {peak:.3f} (Schwelle: {threshold:.3f})")
                # Falls gerade im Fallback-Modus, wechsle wieder in den Audio-Modus.
                if active_mode != "audio":
                    active_mode = "audio"
                # Falls Launchpad verbunden, setze neues Muster
                if connected and lp is not None:
                    try:
                        set_peak_pattern()
                    except Exception as e:
                        print("Error updating peak pattern:", e)
                # Erhöhe den Schwellenwert nur, wenn der letzte Spike weniger als 0.3 s zurückliegt
                if current_time - last_detection_time < 0.3:
                    threshold += 0.01
                last_detection_time = current_time
            else:
                # Wenn seit mindestens 3 Sekunden kein signifikanter Peak (<= 0.05) erkannt wurde
                if current_time - last_detection_time >= 3.0 and peak <= 0.05:
                    if active_mode != "fallback":
                        print("Keine Erkennung für 3 Sekunden (Peak sehr niedrig).")
                        if connected and lp is not None:
                            try:
                                for x in range(9):
                                    for y in range(9):
                                        lp.LedCtrlXY(x, y, *random.choice([DEFAULT_COLOR_1, DEFAULT_COLOR_2]))
                            except Exception as e:
                                print("Error setting LEDs to magenta:", e)
                        active_mode = "fallback"
                    last_detection_time = current_time
                # Ansonsten: Jede 0.3 Sekunden ohne Spike wird der Schwellenwert gesenkt
                elif current_time - last_detection_time >= 0.3:
                    threshold = max(threshold - 0.03, 0)
                    print(f"Keine Erkennung. Schwelle gesenkt auf {threshold:.3f}")
            time.sleep(0.001)

###############################################
# Fallback: LED-Animation (lp_cover-Inhalt)
###############################################
def animation_loop():
    global running, paused, connected, lp, active_mode
    color_options = COLOR_PALETTE[2:]  # Alle Farben außer DEFAULT_COLOR
    # Initialisiere die 9x9 LED-Matrix auf DEFAULT_COLOR
    current_colors = {}
    if connected and lp is not None:
        for x in range(9):
            for y in range(9):
                try:
                    lp.LedCtrlXY(x, y, *random.choice([DEFAULT_COLOR_1, DEFAULT_COLOR_2]))
                except Exception as e:
                    print("Fehler bei LED-Initialisierung:", e)
                current_colors[(x, y)] = random.choice([DEFAULT_COLOR_1, DEFAULT_COLOR_2])
    non_magenta_fields = {}  # key: (x,y), value: timestamp

    print("Started LED-Animation (Fallback-Modus). Tray-Menü: Pause/Close")
    while running:
        if not paused and connected and lp is not None:
            # Führe die Animation nur aus, wenn kein Audio-Signal (Fallback) aktiv ist
            if active_mode == "fallback":
                current_time = time.time()
                # Setze LEDs, die länger als 10 s geändert wurden, zurück auf DEFAULT_COLOR
                for (x, y), changed_time in list(non_magenta_fields.items()):
                    if current_time - changed_time >= 10:
                        try:
                            lp.LedCtrlXY(x, y, *random.choice([DEFAULT_COLOR_1, DEFAULT_COLOR_2]))
                        except Exception as e:
                            print("Fehler beim Zurücksetzen der LED:", e)
                        current_colors[(x, y)] = random.choice([DEFAULT_COLOR_1, DEFAULT_COLOR_2])
                        del non_magenta_fields[(x, y)]
                # Wähle einen zufälligen LED und eine zufällige Farbe
                x = random.randint(0, 8)
                y = random.randint(0, 8)
                new_color = random.choice(color_options)
                if current_colors.get((x, y), random.choice([DEFAULT_COLOR_1, DEFAULT_COLOR_2])) != new_color:
                    try:
                        lp.LedCtrlXY(x, y, *new_color)
                    except Exception as e:
                        print("Fehler beim Aktualisieren einer zufälligen LED:", e)
                    current_colors[(x, y)] = new_color
                    non_magenta_fields[(x, y)] = time.time()
                    print(f"Changed LED at ({x}, {y}) to {new_color}")
                time.sleep(random.uniform(0.05, 0.2))
            else:
                # Ist Audio-Modus aktiv, kurz warten (damit Audio-Thread die LEDs steuert)
                time.sleep(0.1)
        else:
            time.sleep(0.2)

###############################################
# Tray-Icon und Steuerung
###############################################
def create_image():
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), "white")
    dc = ImageDraw.Draw(image)
    dc.ellipse((8, 8, width-8, height-8), fill="magenta")
    return image

def toggle_pause(icon, item):
    global paused, lp, connected
    paused = not paused
    if paused:
        print("Paused.")
        disconnect_launchpad()
    else:
        print("Unpaused.")
        # Vor neuem Verbindungsversuch den internen Zustand komplett zurücksetzen
        lp = None
        connected = False
        import sys, importlib
        if "launchpad_py" in sys.modules:
            del sys.modules["launchpad_py"]
        import launchpad_py as launchpad
        threading.Thread(target=connect_launchpad, daemon=True).start()

def exit_program(icon, item):
    icon.stop()
    cleanup()

def cleanup():
    global lp, running
    print("Exiting...")
    if lp is not None and connected:
        try:
            lp.Reset()
            lp.Close()
        except Exception as e:
            print("Fehler beim Cleanup:", e)
    running = False
    sys.exit(0)

###############################################
# Hauptprogramm: Starte Threads und Tray
###############################################
if __name__ == '__main__':
    connect_launchpad()
    audio_thread = threading.Thread(target=audio_analysis_loop, daemon=True)
    audio_thread.start()
    animation_thread = threading.Thread(target=animation_loop, daemon=True)
    animation_thread.start()
    
    # Tray-Icon
    menu = (item('Pause/Unpause (currently bugged, will crash the program)', toggle_pause), item('Close', exit_program))
    tray_icon = pystray.Icon("lp_cover", create_image(), "LP Cover", menu)
    tray_icon.run()