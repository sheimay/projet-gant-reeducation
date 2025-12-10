from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import NumericProperty
from kivy.core.window import Window
from kivy.clock import Clock

from hand_state import HandCalibrator
from serial_reader import SerialHandReader

# Charger le KV
Builder.load_file("game.kv")


class MenuScreen(Screen):
    pass


class GameScreen(Screen):
    car_x = NumericProperty(0)
    scroll_y = NumericProperty(0)
    distance = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._update_event = None
        self.forward_speed = 200  # vitesse du décor (px/s)

        # ---- LECTURE SERIE + CALIB ----
        # ADAPTE LE PORT ICI (très important)
        self.serial_reader = SerialHandReader(
            port="/dev/cu.usbmodem11201",  # <-- à modifier 
            baudrate=115200,
        )
        self.calib = HandCalibrator()

        # Pour filtrer un peu la commande
        self._steer_filtered = 0.0
        self._no_state_logged = False

    def on_kv_post(self, base_widget):
        # Initialisation après chargement du KV
        self.car_x = self.width / 2
        self.scroll_y = 0
        self.distance = 0

    def on_pre_enter(self, *args):
        print(">>> ON ENTRE DANS GameScreen")

        # clavier (optionnel, pour tester)
        Window.bind(on_key_down=self.on_key_down)

        # Démarrer la lecture série
        try:
            self.serial_reader.start()
            print(">>> SerialHandReader démarré")
        except Exception as e:
            print(f"ERREUR ouverture port série: {e}")

        # Boucle de mise à jour
        self._update_event = Clock.schedule_interval(self.update_game, 1 / 60)

    def on_leave(self, *args):
        Window.unbind(on_key_down=self.on_key_down)
        self.serial_reader.stop()
        if self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None

    def on_size(self, *args):
        # Recentrer la voiture si la fenêtre change de taille
        self.car_x = self.width / 2

    # --- Contrôle clavier pour debug (flèches gauche/droite) ---
    def on_key_down(self, window, key, scancode, codepoint, modifiers):
        if key == 276:      # gauche
            self.move_car_pixels(-40)  # 40 px par pression
        elif key == 275:    # droite
            self.move_car_pixels(40)

    # --- Mouvement de la voiture en pixels ---
    def move_car_pixels(self, delta_px: float):
        self.car_x += delta_px
        self._clamp_car()

    def update_game(self, dt):
        # 1) Scroll du fond (comme avant)
        if self.height > 0:
            self.scroll_y -= self.forward_speed * dt
            if self.scroll_y <= -self.height:
                self.scroll_y += self.height

        self.distance += (self.forward_speed * dt) / 100.0

        # 2) Lecture de l'état de la main
        state = self.serial_reader.get_latest_state()

        if state is None:
            # Affiche une seule fois qu'on n'a pas encore de données
            if not self._no_state_logged:
                print(">>> Aucun HandState reçu pour le moment.")
                self._no_state_logged = True
            return

        # Si on arrive ici, on a bien des données
        self._no_state_logged = False

        # 3) Commande de direction à partir du gyroscope
        # steering_from_gyro renvoie une valeur dans [-1, +1]
        # On utilise gy comme axe par défaut
        steer_raw = state.steering_from_gyro(sensitivity_deg_per_s=45.0)
        # 45.0 => très sensible. Tu pourras augmenter à 60 ou 90 plus tard.

        # Filtre exponentiel pour lisser un peu
        alpha = 0.3
        self._steer_filtered = (1 - alpha) * self._steer_filtered + alpha * steer_raw

       
        # 4) Application à la position de la voiture
        # Gain fort pour bien voir l'effet
        # self._steer_filtered ∈ [-1,1]
        # On veut pouvoir aller de gauche à droite assez vite
        gain_px_per_sec = 400  # px/s pour steer=1.0
        delta_px = self._steer_filtered * gain_px_per_sec * dt
        self.move_car_pixels(delta_px)

    def _clamp_car(self):
        margin = self.width * 0.05
        if self.car_x < margin:
            self.car_x = margin
        if self.car_x > self.width - margin:
            self.car_x = self.width - margin


class GantJeuApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MenuScreen(name="menu"))
        sm.add_widget(GameScreen(name="game"))
        return sm


if __name__ == "__main__":
    GantJeuApp().run()
