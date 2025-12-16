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
        self._phase = 0
        self._open_samples: list[HandState] = []

        

    def _calib_path(self) -> str:
        # Simple: fichier dans le dossier du projet
        return os.path.join(os.getcwd(), "calibration.txt")

    def on_pre_enter(self):
        self.progress = 0.0
        self.calibrated = False
        self.status = "Posez la main au repos puis cliquez sur Démarrer."
        self._phase = 0
        self._open_samples.clear()
        self.status = "Main ouverte (repos). Cliquez sur Démarrer."


    def start_calibration(self):
        app = App.get_running_app()
        if not hasattr(app, "calib"):
            app.calib = HandCalibrator()

        # utilise le même port que ta voiture si tu veux
        if self.serial_reader is None:
            self.serial_reader = SerialHandReader(
                port="/dev/cu.usbmodem1201",  # <-- mets le même que GameScreen
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
            self.status = "Aucune donnée reçue."
            return

        # Phase 0 : main ouverte (min + offsets)
        if self._phase == 0:
            self._open_samples = self._samples[:]
            self._samples = []
            self._phase = 1
            self.progress = 0.0
            self.status = "OK. Maintenant main fermée (flexion max) puis cliquez sur Démarrer."
            return

        # Phase 1 : main fermée (max)
        closed_samples = self._samples[:]

        app = App.get_running_app()
        if not hasattr(app, "calib") or app.calib is None:
            app.calib = HandCalibrator()
        calib: HandCalibrator = app.calib

        # --- calc moyennes ---
        def avg(vals):
            return sum(vals) / float(len(vals))

        open_s = self._open_samples
        n1 = len(open_s)
        n2 = len(closed_samples)
    # calibration_screen.py, dans _finish(), après calcul open_s

        calib.flex_thumb_rest = avg([s.flex_thumb for s in open_s])
        calib.flex_index_rest = avg([s.flex_index for s in open_s])
        calib.fsr_thumb_rest  = avg([s.fsr_thumb  for s in open_s])
        calib.fsr_index_rest  = avg([s.fsr_index  for s in open_s])

        flex_thumb_min = avg([s.flex_thumb for s in open_s])
        flex_index_min = avg([s.flex_index for s in open_s])
        fsr_thumb_min  = avg([s.fsr_thumb  for s in open_s])
        fsr_index_min  = avg([s.fsr_index  for s in open_s])

        flex_thumb_max = avg([s.flex_thumb for s in closed_samples])
        flex_index_max = avg([s.flex_index for s in closed_samples])
        fsr_thumb_max  = avg([s.fsr_thumb  for s in closed_samples])
        fsr_index_max  = avg([s.fsr_index  for s in closed_samples])



        # --- affectation bornes ---
        calib.flex_thumb_min = flex_thumb_min
        calib.flex_thumb_max = flex_thumb_max
        calib.flex_index_min = flex_index_min
        calib.flex_index_max = flex_index_max

        calib.fsr_thumb_min = fsr_thumb_min
        calib.fsr_thumb_max = fsr_thumb_max
        calib.fsr_index_min = fsr_index_min
        calib.fsr_index_max = fsr_index_max

        # --- offsets gyro (repos) ---
        calib.gx_offset = avg([s.gx for s in open_s])
        calib.gy_offset = avg([s.gy for s in open_s])
        calib.gz_offset = avg([s.gz for s in open_s])

        # (optionnel) seuils par défaut (normalisés)
        calib.index_threshold = getattr(calib, "index_threshold", 0.6)
        calib.majeur_threshold = getattr(calib, "majeur_threshold", 0.6)
        calib.thumb_fsr_threshold = getattr(calib, "thumb_fsr_threshold", 0.6)
        calib.index_fsr_threshold = getattr(calib, "index_fsr_threshold", 0.6)

        # Sauvegarde TXT
        path = self._calib_path()
        calib.save_txt(path)

        self.calibrated = True
        self.status = f"Calibration OK ✅ (open+closed) sauvegardée: {os.path.basename(path)}"

    def go_menu(self):
        App.get_running_app().root.current = "menu"
