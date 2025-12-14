# jump_game.py

from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty, BooleanProperty
from kivy.clock import Clock

from serial_reader import SerialHandReader
from hand_state import HandState

# Mets True quand tu voudras tester avec l'Arduino branché
USE_ARDUINO = False


def _norm(value, vmin, vmax):
    """Normalise value entre 0 et 1 (saturation)."""
    if vmax <= vmin:
        return 0.0
    x = (value - vmin) / float(vmax - vmin)
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


class JumpGameScreen(Screen):
    # Debug UI (facultatif)
    thumb_active = BooleanProperty(False)
    index_active = BooleanProperty(False)
    pinch_active = BooleanProperty(False)

    score = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if USE_ARDUINO:
            self.serial_reader = SerialHandReader(port="COM3", baudrate=115200)
        else:
            self.serial_reader = None

        # -------- Réglages détection pince --------
        self.THUMB_T = 0.6          # seuil (normalisé 0..1)
        self.INDEX_T = 0.6
        self.SYNC_WINDOW = 0.20     # secondes (200 ms)

        # TODO: adapte ces min/max avec tes vraies pressions
        self.P_MIN = 100            # pression au repos
        self.P_MAX = 900            # pression forte

        # -------- États internes --------
        self._t = 0.0               # temps interne (seconds)
        self._thumb_press_time = None
        self._index_press_time = None
        self._was_pinch = False

        # Cooldown optionnel (évite les doubles sauts même si bruit)
        self.JUMP_COOLDOWN = 0.25
        self._last_jump_time = -999.0

        # Avatar simple (physique minimaliste)
        self.y = 0.0
        self.vy = 0.0
        self.gravity = -1800.0      # px/s²
        self.jump_impulse = 750.0   # px/s
        self.ground_y = 0.0

    def on_pre_enter(self):
        print(">>> JUMP SCREEN OPENED <<<")

        self.score = 0
        self._t = 0.0
        self._thumb_press_time = None
        self._index_press_time = None
        self._was_pinch = False
        self._last_jump_time = -999.0

        self.y = self.ground_y
        self.vy = 0.0

        if self.serial_reader is not None:
            self.serial_reader.start()

        Clock.schedule_interval(self.update_game, 1.0 / 60.0)

    def on_leave(self):
        Clock.unschedule(self.update_game)
        if self.serial_reader is not None:
            self.serial_reader.stop()

    # ------------------ Détection pince ------------------

    def _read_pressures(self, state: HandState):
        """
        Lecture des capteurs de pression :
      - fsr_thumb : pouce
      - fsr_index : index
    """
        thumb_raw = state.fsr_thumb
        index_raw = state.fsr_index

        thumb_n = _norm(thumb_raw, self.P_MIN, self.P_MAX)
        index_n = _norm(index_raw, self.P_MIN, self.P_MAX)
        return thumb_n, index_n

    def _pinch_event(self, thumb_n: float, index_n: float) -> bool:
        """
        Retourne True UNIQUEMENT au moment où la pince est détectée (front montant).
        """
        thumb_pressed = thumb_n > self.THUMB_T
        index_pressed = index_n > self.INDEX_T

        # debug UI
        self.thumb_active = thumb_pressed
        self.index_active = index_pressed

        # mémorise le moment où chaque doigt dépasse le seuil
        if thumb_pressed and self._thumb_press_time is None:
            self._thumb_press_time = self._t
        if index_pressed and self._index_press_time is None:
            self._index_press_time = self._t

        # relâchement => réarmement des temps
        if not thumb_pressed:
            self._thumb_press_time = None
        if not index_pressed:
            self._index_press_time = None

        # pince “valide” si les deux sont pressés et arrivés dans la fenêtre
        pinch_now = False
        if thumb_pressed and index_pressed and self._thumb_press_time is not None and self._index_press_time is not None:
            if abs(self._thumb_press_time - self._index_press_time) <= self.SYNC_WINDOW:
                pinch_now = True

        self.pinch_active = pinch_now

        # front montant + cooldown anti-bruit
        if pinch_now and not self._was_pinch and (self._t - self._last_jump_time) >= self.JUMP_COOLDOWN:
            self._was_pinch = True
            self._last_jump_time = self._t
            return True

        if not pinch_now:
            self._was_pinch = False

        return False

    # ------------------ Mécanique saut ------------------

    def do_jump(self):
        # saute uniquement si au sol
        if self.y <= self.ground_y + 1.0:
            self.vy = self.jump_impulse

    def update_physics(self, dt: float):
        # gravité
        self.vy += self.gravity * dt
        self.y += self.vy * dt

        # sol
        if self.y < self.ground_y:
            self.y = self.ground_y
            self.vy = 0.0

    # ------------------ Boucle jeu ------------------

    def update_game(self, dt: float):
        self._t += dt

        # sans Arduino: tu peux simuler rien (ou clavier plus tard)
        if self.serial_reader is None:
            self.update_physics(dt)
            return

        state = self.serial_reader.get_latest_state()
        if state is None:
            self.update_physics(dt)
            return

        thumb_n, index_n = self._read_pressures(state)
        if thumb_n is None:
            self.update_physics(dt)
            return

        # détection pince => jump
        if self._pinch_event(thumb_n, index_n):
            self.do_jump()
            self.score += 1  # ou score par obstacle plus tard

        self.update_physics(dt)
