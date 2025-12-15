# calibration_screen.py
import os
from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty, StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.app import App

from serial_reader import SerialHandReader
from hand_state import HandState, HandCalibrator


class CalibrationScreen(Screen):
    progress = NumericProperty(0.0)
    status = StringProperty("Posez la main au repos puis cliquez sur Démarrer.")
    calibrated = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.serial_reader: SerialHandReader | None = None
        self._evt = None
        self._t = 0.0
        self._duration = 3.0
        self._samples: list[HandState] = []

    def _calib_path(self) -> str:
        # Simple: fichier dans le dossier du projet
        return os.path.join(os.getcwd(), "calibration.txt")

    def on_pre_enter(self):
        self.progress = 0.0
        self.calibrated = False
        self.status = "Posez la main au repos puis cliquez sur Démarrer."

    def start_calibration(self):
        app = App.get_running_app()
        if not hasattr(app, "calib"):
            app.calib = HandCalibrator()

        # utilise le même port que ta voiture si tu veux
        if self.serial_reader is None:
            self.serial_reader = SerialHandReader(
                port="/dev/cu.usbmodem1101",  # <-- mets le même que GameScreen
                baudrate=115200
            )

        try:
            self.serial_reader.start()
        except Exception as e:
            self.status = f"Erreur port série: {e}"
            return

        self._samples.clear()
        self._t = 0.0
        self.progress = 0.0
        self.calibrated = False
        self.status = "Calibration en cours… ne bougez pas."

        if self._evt is not None:
            self._evt.cancel()
        self._evt = Clock.schedule_interval(self._collect, 1.0 / 60.0)

    def _collect(self, dt: float):
        self._t += dt
        self.progress = min(1.0, self._t / self._duration)

        state = self.serial_reader.get_latest_state() if self.serial_reader else None
        if state is not None:
            self._samples.append(state)

        if self._t >= self._duration:
            self._finish()
            return False  # stop schedule
        return True

    def _finish(self):
        if self.serial_reader is not None:
            self.serial_reader.stop()

        if not self._samples:
            self.status = "Aucune donnée reçue. Vérifiez le port série."
            self.progress = 0.0
            return

        app = App.get_running_app()
        calib: HandCalibrator = app.calib

        n = len(self._samples)
        calib.flex_thumb_rest = sum(s.flex_thumb for s in self._samples) / n
        calib.flex_index_rest = sum(s.flex_index for s in self._samples) / n
        calib.fsr_thumb_rest = sum(s.fsr_thumb for s in self._samples) / n
        calib.fsr_index_rest = sum(s.fsr_index for s in self._samples) / n
        calib.gx_offset = sum(s.gx for s in self._samples) / n
        calib.gy_offset = sum(s.gy for s in self._samples) / n
        calib.gz_offset = sum(s.gz for s in self._samples) / n

        # Sauvegarde TXT
        path = self._calib_path()
        calib.save_txt(path)

        self.calibrated = True
        self.status = f"Calibration OK ✅ (sauvegardée: {os.path.basename(path)})"

    def go_menu(self):
        App.get_running_app().root.current = "menu"
