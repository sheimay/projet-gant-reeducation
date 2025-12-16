from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty, BooleanProperty
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.app import App

from serial_reader import SerialHandReader
from hand_state import HandState

USE_ARDUINO = True
SERIAL_PORT = "/dev/cu.usbmodem1201"
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
        self._bg_inited = False
        self._t = 0.0

        # --------- Série Arduino ----------
        self.serial_reader: SerialHandReader | None = None
        if USE_ARDUINO:
            self.serial_reader = SerialHandReader(port=SERIAL_PORT, baudrate=SERIAL_BAUD)

       # --------- Détection appui (FSR index seul) ----------
        self.INDEX_T = 0.30          # seuil normalisé (0..1) - sera écrasé par calibration si dispo
        self.P_MIN = 100             # fallback si pas de calibration
        self.P_MAX = 900

        self._was_pressed = False
        self.JUMP_COOLDOWN = 0.25
        self._last_jump_time = -999.0

        # Debug print rate-limit
        self._dbg_timer = 0.0

        # --------- Physique saut ----------
        self.vy = 0.0
        self.gravity = -1800.0
        self.ground_y = dp(100)

        # ===== Saut à amplitude variable =====
        self.min_impulse = 520.0
        self.max_impulse = 980.0
        self.strength_exp = 1.3
        self.last_pinch_strength = 0.0

        # Debug print rate-limit
        self._dbg_timer = 0.0

        self._keyboard_bound = False

    # ============================================================
    # Fond défilant
    # ============================================================

    def on_size(self, *args):
        if self.width <= 1:
            return
        if not self._bg_inited:
            self.bg1_x = 0
            self.bg2_x = self.width
            self._bg_inited = True

    def update_background(self, dt: float):
        if not self._bg_inited or self.width <= 1:
            return
        w = self.width
        self.bg1_x -= self.scroll_speed * dt
        self.bg2_x -= self.scroll_speed * dt
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
        self._last_jump_time = -999.0

        self.avatar_y = self.ground_y
        self.vy = 0.0

        self._dbg_timer = 0.0

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
            self.do_jump(1.0)
            return True
        return False

    # ============================================================
    # Détection pince (Arduino) + calibration Kivy
    # ============================================================

    def _get_calib(self):
        app = App.get_running_app()
        return getattr(app, "calib", None)

    def _read_index_pressure(self, state: HandState) -> float:
        """
        ATTENTION HARDWARE:
        Le FSR index est physiquement branché sur A2,
        mais à cause d'un défaut de soudure Arduino,
        la valeur arrive dans la 4e colonne du serial => fsr_thumb.
        """
        calib = self._get_calib()

        if calib is None:
            index_n = _norm(state.fsr_thumb, self.P_MIN, self.P_MAX)
        else:
            index_n = _norm(
                state.fsr_thumb,
                calib.fsr_thumb_min,
                calib.fsr_thumb_max
            )
            self.INDEX_T = getattr(calib, "index_fsr_threshold", self.INDEX_T)

        return index_n



    def _press_event(self, index_n: float) -> tuple[bool, float]:
        pressed = index_n > self.INDEX_T
        self.index_active = pressed     # pour debug UI si tu l’utilises

        # front montant + cooldown
        if pressed and (not self._was_pressed) and (self._t - self._last_jump_time) >= self.JUMP_COOLDOWN:
            self._was_pressed = True
            self._last_jump_time = self._t
            return True, index_n  # strength = index_n (0..1)

        if not pressed:
            self._was_pressed = False

        return False, 0.0


    # ============================================================
    # Physique saut
    # ============================================================

    def do_jump(self, strength: float = 1.0):
        """Saute seulement si l’avatar est au sol, avec amplitude variable."""
        if self.avatar_y <= self.ground_y + 200.0:
            s = max(0.0, min(1.0, strength))
            s = s ** self.strength_exp
            impulse = self.min_impulse + s * (self.max_impulse - self.min_impulse)
            self.vy = impulse
            #print("DO JUMP", self.vy)



    def update_physics(self, dt: float):
        self.vy += self.gravity * dt
        self.avatar_y += self.vy * dt

        if self.avatar_y < self.ground_y:
            self.avatar_y = self.ground_y
            self.vy = 0.0

        """# DEBUG: 5 Hz
        self._dbg_timer += dt
        if self._dbg_timer >= 0.2:
            av_y = self.avatar_y
            img_y = self.ids.avatar.y if "avatar" in self.ids else -1
            print(f"[PHYS] vy={self.vy:.1f}  avatar_y={av_y:.1f}  image_y={img_y:.1f}")
            self._dbg_timer = 0.0
"""

    # ============================================================
    # Boucle jeu
    # ============================================================

    def update_game(self, dt: float):
        self._t += dt

        # Fond
        self.update_background(dt)

        # Si pas d'Arduino, juste physique
        if self.serial_reader is None:
            self.update_physics(dt)
            return

        state = self.serial_reader.get_latest_state()
        if state is None:
            self.update_physics(dt)
            return

        # Lecture FSR index + calibration
        index_n = self._read_index_pressure(state)

        # Debug (5 Hz)
        """self._dbg_timer += dt
        if self._dbg_timer >= 0.2:
            print(
                f"FSR INDEX RAW -> {state.fsr_thumb} | "
                f"NORM -> {index_n:.3f} | T -> {self.INDEX_T:.2f}"
            )
            self._dbg_timer = 0.0"""

        # Appui -> jump
        pressed, strength = self._press_event(index_n)
        if pressed:
            self.do_jump(strength)
            self.score += 1

        # <<< FIX CRITIQUE : la physique DOIT toujours s’exécuter
        self.update_physics(dt)


