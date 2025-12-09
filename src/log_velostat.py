import serial
import time
import numpy as np
import matplotlib.pyplot as plt


SERIAL_PORT = "/dev/tty.usbmodem11301"  # <-- remplace par TON port
BAUD_RATE = 115200
OUTPUT_FILE = "velostat_data.txt"

# -------------------------------

def main():
    print(f"Ouverture du port série {SERIAL_PORT} à {BAUD_RATE} bauds...")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

    # On ouvre le fichier en écriture (écrase l'ancien si existe)
    with open(OUTPUT_FILE, "w") as f:
        # En-tête (facultatif)
        f.write("# time_s tension_V\n")

        print(f"Enregistrement dans '{OUTPUT_FILE}' (Ctrl+C pour arrêter).")

        # Référence de temps (t=0 au démarrage de l’acquisition)
        t0 = time.time()

        try:
            while True:
                line = ser.readline().decode(errors="ignore").strip()

                # On ignore les lignes vides ou non numériques (ex: "START")
                if not line:
                    continue
                try:
                    tension = float(line)
                except ValueError:
                    continue  # ignore les lignes non numériques

                t = time.time() - t0  # temps relatif en secondes

                # Écriture dans le fichier : 2 colonnes séparées par un espace
                f.write(f"{t:.3f} {tension:.4f}\n")
                f.flush()

                # Petit affichage console pour contrôle
                print(f"{t:.3f}s  {tension:.4f} V")

        except KeyboardInterrupt:
            print("\nArrêt demandé par l'utilisateur (Ctrl+C).")

    ser.close()
    print("Port série fermé. Fichier sauvegardé.")

if __name__ == "__main__":
    main()



data = np.loadtxt("velostat_data.txt")
t = data[:, 0]
v = data[:, 1]

plt.plot(t, v)
plt.xlabel("Temps (s)")
plt.ylabel("Tension (V)")
plt.title("Évolution de la tension velostat")
plt.grid(True)
plt.show()
