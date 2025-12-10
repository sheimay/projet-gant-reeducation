# serial_reader.py

import threading
from typing import Optional

import serial

from hand_state import HandState


class SerialHandReader:
    """
    Lit en continu les lignes du port série et expose le dernier HandState.
    """

    def __init__(self, port: str, baudrate: int = 115200):
        self.port_name = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.thread: Optional[threading.Thread] = None
        self.running: bool = False

        self._lock = threading.Lock()
        self._latest_state: Optional[HandState] = None

    def start(self):
        """
        Ouvre le port série et lance le thread de lecture.
        """
        self.ser = serial.Serial(self.port_name, self.baudrate, timeout=1)
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        """
        Arrête le thread et ferme le port.
        """
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None

        if self.ser is not None:
            self.ser.close()
            self.ser = None

    def _loop(self):
        """
        Boucle de lecture dans un thread séparé.
        """
        assert self.ser is not None
        while self.running:
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode(errors="ignore").strip()
                state = HandState.from_csv_line(line)
                if state is not None:
                    with self._lock:
                        self._latest_state = state
            except Exception:
                # On ignore simplement les erreurs de parsing ou de lecture
                continue

    def get_latest_state(self) -> Optional[HandState]:
        """
        Renvoie le dernier état de la main reçu (ou None si rien encore).
        """
        with self._lock:
            return self._latest_state
