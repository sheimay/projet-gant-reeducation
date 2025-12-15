from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty, BooleanProperty
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.app import App


from serial_reader import SerialHandReader
from hand_state import HandState

USE_ARDUINO = False
SERIAL_PORT = "COM3"
SERIAL_BAUD = 115200


def _norm(value: float, vmin: float, vmax: float) -> float:
    if vmax <= vmin:
        return 0.0
    x = (value - vmin) / float(vmax - vmin)
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


class JumpGameScreen(Screen):

    # ===== Fond défilant (bind KV) =====
    bg1_x = NumericProperty(0.0)
    bg2_x = NumericProperty(0.0)
    scroll_speed = NumericProperty(220.0)  # px/s

    # ===== UI / Game =====
    score = NumericProperty(0)

    # Avatar (bind KV)
    avatar_y = NumericProperty(0.0)
    avatar_x = NumericProperty(0.0)

    # (si ton KV les utilise)
    avatar_baseline = NumericProperty(0.0)
    avatar_left_trim = NumericProperty(0.0)

    # Debug pinch
    thumb_active = BooleanProperty(False)
    index_active = BooleanProperty(False)
    pinch_active = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Pour éviter que on_size ré-initialise en boucle
        self._bg_inited = False

        # --------- Série Arduino ----------
        self.serial_reader: SerialHandReader | None = None
        if USE_ARDUINO:
            self.serial_reader = SerialHandReader(port=SERIAL_PORT, baudrate=SERIAL_BAUD)

        # --------- Détection pince (FSR pouce + index) ----------
        self.THUMB_T = 0.60
        self.INDEX_T = 0.60
        self.SYNC_WINDOW = 0.20

        self.P_MIN = 100
        self.P_MAX = 900

        self._t = 0.0
        self._thumb_press_time: float | None = None
        self._index_press_time: float | None = None
        self._was_pinch = False

        self.JUMP_COOLDOWN = 0.25
        self._last_jump_time = -999.0

        # --------- Physique saut ----------
        self.vy = 0.0
        self.gravity = -1800.0
        self.jump_impulse = 750.0
        self.ground_y = dp(100)

        # ===== Saut à amplitude variable =====
        self.min_impulse = 520.0     # petit saut
        self.max_impulse = 980.0     # grand saut
        self.strength_exp = 1.3      # courbe de sensibilité (1.0 = linéaire)
        self.last_pinch_strength = 0.0


        self._keyboard_bound = False

    # ============================================================
    # Fond défilant
    # ============================================================

    def on_size(self, *args):
        """
        Appelé quand la taille de l'écran change.
        On initialise le fond UNE SEULE FOIS quand width est valide.
        """
        if self.width <= 1:
            return

        if not self._bg_inited:
            self.bg1_x = 0
            self.bg2_x = self.width
            self._bg_inited = True

    def update_background(self, dt: float):
        """Défilement + boucle infinie."""
        # Si pas encore initialisé (ex: width==0 au départ), on n’avance pas
        if not self._bg_inited or self.width <= 1:
            return

        w = self.width

        self.bg1_x -= self.scroll_speed * dt
        self.bg2_x -= self.scroll_speed * dt

        # Rebouclage
        if self.bg1_x <= -w:
            self.bg1_x = self.bg2_x + w

        if self.bg2_x <= -w:
            self.bg2_x = self.bg1_x + w

    # ============================================================
    # Lifecycle
    # ============================================================

    def on_pre_enter(self):
        print(">>> JUMP SCREEN OPENED <<<")

        self.score = 0
        self._t = 0.0
        self._thumb_press_time = None
        self._index_press_time = None
        self._was_pinch = False
        self._last_jump_time = -999.0

        self.avatar_y = self.ground_y
        self.vy = 0.0

        if self.serial_reader is not None:
            self.serial_reader.start()

        if not self._keyboard_bound:
            Window.bind(on_key_down=self._on_key_down)
            self._keyboard_bound = True

        Clock.schedule_interval(self.update_game, 1.0 / 60.0)

    def on_leave(self):
        Clock.unschedule(self.update_game)

        if self.serial_reader is not None:
            self.serial_reader.stop()

        if self._keyboard_bound:
            Window.unbind(on_key_down=self._on_key_down)
            self._keyboard_bound = False

    # ============================================================
    # Input clavier (test)
    # ============================================================

    def _on_key_down(self, window, keycode, scancode, codepoint, modifiers):
        if keycode and len(keycode) > 1 and keycode[1] == "space":
            self.do_jump()
            return True
        return False

    # ============================================================
    # Détection pince (Arduino)
    # ============================================================

    def _read_pressures(self, state: HandState) -> tuple[float, float]:
        calib = getattr(App.get_running_app(), "calib", None)
        if calib is None:
            thumb_n = _norm(state.fsr_thumb, self.P_MIN, self.P_MAX)
            index_n = _norm(state.fsr_index, self.P_MIN, self.P_MAX)
        else:
            thumb_n = _norm(state.fsr_thumb, calib.fsr_thumb_min, calib.fsr_thumb_max)
            index_n = _norm(state.fsr_index, calib.fsr_index_min, calib.fsr_index_max)

        # (optionnel) seuils adaptables
            self.THUMB_T = getattr(calib, "thumb_fsr_threshold", self.THUMB_T)
            self.INDEX_T = getattr(calib, "index_fsr_threshold", self.INDEX_T)

        return thumb_n, index_n

    def _pinch_event(self, thumb_n: float, index_n: float):

        thumb_pressed = thumb_n > self.THUMB_T
        index_pressed = index_n > self.INDEX_T

        self.thumb_active = thumb_pressed
        self.index_active = index_pressed

        if thumb_pressed and self._thumb_press_time is None:
            self._thumb_press_time = self._t
        if index_pressed and self._index_press_time is None:
            self._index_press_time = self._t

        if not thumb_pressed:
            self._thumb_press_time = None
        if not index_pressed:
            self._index_press_time = None

        pinch_now = False
        if (
            thumb_pressed and index_pressed
            and self._thumb_press_time is not None
            and self._index_press_time is not None
            and abs(self._thumb_press_time - self._index_press_time) <= self.SYNC_WINDOW
        ):
            pinch_now = True

        self.pinch_active = pinch_now
        strength = min(thumb_n, index_n)  # 0..1 (le doigt le plus faible limite)

        if pinch_now and (not self._was_pinch) and (self._t - self._last_jump_time) >= self.JUMP_COOLDOWN:
            self._was_pinch = True
            self._last_jump_time = self._t
            self.last_pinch_strength = strength
            return True, strength

        if not pinch_now:
            self._was_pinch = False

        return False, 0.0

    # ============================================================
    # Physique saut
    # ============================================================

    def do_jump(self, strength: float = 1.0):
        """Saute seulement si l’avatar est au sol, avec amplitude variable."""
        if self.avatar_y <= self.ground_y + 1.0:
            s = max(0.0, min(1.0, strength))   # clamp 0..1
            s = s ** self.strength_exp         # courbe (progressif)

            impulse = self.min_impulse + s * (self.max_impulse - self.min_impulse)
            self.vy = impulse

    def update_physics(self, dt: float):
        self.vy += self.gravity * dt
        self.avatar_y += self.vy * dt

        if self.avatar_y < self.ground_y:
            self.avatar_y = self.ground_y
            self.vy = 0.0

    # ============================================================
    # Boucle jeu
    # ============================================================

    def update_game(self, dt: float):
        self._t += dt

        # ✅ fond animé
        self.update_background(dt)

        # Arduino OFF
        if self.serial_reader is None:
            self.update_physics(dt)
            return

        state = self.serial_reader.get_latest_state()
        if state is None:
            self.update_physics(dt)
            return

        thumb_n, index_n = self._read_pressures(state)

        pinched, strength = self._pinch_event(thumb_n, index_n)
        if pinched:
            self.do_jump(strength)
            self.score += 1

        self.update_physics(dt)
