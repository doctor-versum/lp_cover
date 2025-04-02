import time
import soundcard as sc
import numpy as np
import launchpad_py as launchpad
import random

# Initialisiere Launchpad
lp = launchpad.LaunchpadMiniMk3()
lp.Open()
lp.Reset()

sample_rate = 48000
chunk_size = 1024           # Anzahl der Frames pro Chunk
threshold = 0.40            # Initialer Schwellenwert für Spike-Erkennung

# Frequenzbereich definieren (in Hz)
f_min = 400
f_max = 1000

mic = sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True)
with mic.recorder(samplerate=sample_rate) as recorder:
    print("Starte Live-Audioanalyse. Drücke Strg+C zum Beenden.")
    # Diese Variable wird nur bei tatsächlicher Spike-Erkennung aktualisiert.
    last_detection_time = time.time()
    try:
        while True:
            current_time = time.time()
            data = recorder.record(numframes=chunk_size)
            # Analyse des ersten Kanals
            channel_data = data[:, 0]

            # FFT durchführen
            fft_data = np.fft.rfft(channel_data)
            freqs = np.fft.rfftfreq(len(channel_data), d=1/sample_rate)

            # Nur den gewünschten Frequenzbereich betrachten
            band_mask = (freqs >= f_min) & (freqs <= f_max)
            # FFT-Ergebnisse normieren
            magnitudes = np.abs(fft_data[band_mask]) / chunk_size
            peak = (magnitudes.max() if magnitudes.size > 0 else 0) * 5

            if peak > threshold:
                print(f"Spike erkannt: {peak:.3f} (Schwelle: {threshold:.3f})")
                lp.LedAllOn(random.randint(1, 127))
                # Erhöhe den Schwellenwert nur, wenn der letzte Detektionszeitpunkt weniger als 0.3 s zurückliegt
                if current_time - last_detection_time < 0.3:
                    threshold += 0.01
                last_detection_time = current_time  # Bei Erkennung aktualisieren
            else:
                # Wenn seit mindestens 3 Sekunden nichts (Peak <= 0.05) erkannt wurde
                if current_time - last_detection_time >= 3.0 and peak <= 0.05:
                    print("Keine Erkennung für 3 Sekunden (Peak sehr niedrig).")
                    lp.LedAllOn(0)  # Lichter ausschalten
                    last_detection_time = current_time  # Hier aktualisieren wir, um den Off-Zustand nicht ständig neu auszulösen
                # Ansonsten: Jede 0.3 Sekunden ohne Spike wird der Schwellenwert gesenkt
                elif current_time - last_detection_time >= 0.3:
                    threshold = max(threshold - 0.05, 0)
                    print(f"Keine Erkennung. Schwelle gesenkt auf {threshold:.3f}")
                    # Wir aktualisieren hier nicht last_detection_time, damit 3s-Check weiterhin greift
            # Optional: Eine kleine Pause, um CPU-Last zu reduzieren
            time.sleep(0.001)
    except KeyboardInterrupt:
        print("Live-Audioanalyse beendet.")