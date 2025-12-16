from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import NumericProperty
from kivy.core.window import Window
from kivy.clock import Clock
import random
from collections import deque
from math import fmod
from kivy.uix.image import Image
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.factory import Factory


from calibration_screen import CalibrationScreen
from hand_state import HandCalibrator
from serial_reader import SerialHandReader
from piano_game import PianoGameScreen
from jump_game import JumpGameScreen
from graph import WristFollowUpScreen, FlexFollowUpScreen, PressureFollowUpScreen
from hand3d import Hand3DView



Factory.register("Hand3DView", cls=Hand3DView)

# Charger le KV
Builder.load_file("game.kv")


class MenuScreen(Screen):
    pass
class FollowUpScreen(Screen):
    pass

from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.app import App

from collections import deque
from math import fmod

from serial_reader import SerialHandReader

# Graph Kivy Garden
from kivy_garden.graph import Graph, LinePlot

USE_ARDUINO = True
SERIAL_PORT = "/dev/cu.usbmodem1201"
SERIAL_BAUD = 115200


class GameScreen(Screen):
    car_x = NumericProperty(0)
    scroll_y = NumericProperty(0)
    distance = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._update_event = None
        self.forward_speed = 200  # vitesse du décor (px/s)
        self.obstacles = []           # liste d'Image obstacles
        self.spawn_timer = 0.0
        self.spawn_every = 1.2        # secondes (diminue => + d’obstacles)


        # ---- LECTURE SERIE + CALIB ----
        # ADAPTE LE PORT ICI (très important)
        self.serial_reader = SerialHandReader(
            port="/dev/cu.usbmodem1201",  # <-- à modifier 
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
        layer = self.ids.get("obstacles_layer")
        if layer:
            layer.clear_widgets()
            self.obstacles.clear()


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

    def get_road_bounds(self):
        road_width_ratio = 0.40  # ajuste si besoin
        center_x = self.width / 2
        road_width = self.width * road_width_ratio
        left = center_x - road_width / 2
        right = center_x + road_width / 2
        return left, right
    
    def spawn_obstacle(self):
        layer = self.ids.obstacles_layer

    # Zone "route" (à ajuster selon ton background)
        road_left, road_right = self.get_road_bounds()
        road_width = road_right - road_left

    # --- Lanes (positions RELATIVES dans la route) ---
    # 0.25 = gauche | 0.5 = centre | 0.75 = droite
        lanes = [0.3,0.5, 0.7]
        lane = random.choice(lanes)
        size = dp(random.choice([55, 65, 75]))
        x = random.uniform(road_left, road_right - size)
        y = self.height + size

    # 👉 ICI : choix aléatoire de l'obstacle
        source = random.choice([
        "assets/obstacle_cone.png",
        "assets/obstacle_pothole.png",
        ])

        obs = Image(
            source=source,   # ← on utilise le choix ici
            size_hint=(None, None),
            size=(size, size),
            pos=(x, y),
            allow_stretch=True,
            keep_ratio=True,
        )

        layer.add_widget(obs)
        self.obstacles.append(obs)
    
    def update_game(self, dt):
    # 1) Scroll fond
        if self.height > 0:
            self.scroll_y -= self.forward_speed * dt
            if self.scroll_y <= -self.height:
                self.scroll_y += self.height
        self.distance += (self.forward_speed * dt) / 100.0

    # 2) Obstacles (spawn + move) -> TOUJOURS, même si state None
        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_every:
            self.spawn_timer = 0.0
            self.spawn_obstacle()

        to_remove = []
        for obs in self.obstacles:
            obs.y -= self.forward_speed * dt
            if obs.top < 0:
                to_remove.append(obs)

        for obs in to_remove:
            self.ids.obstacles_layer.remove_widget(obs)
            self.obstacles.remove(obs)

    # 3) Lecture main (peut être None)
        state = self.serial_reader.get_latest_state()
        if state is None:
            if not self._no_state_logged:
                print(">>> Aucun HandState reçu pour le moment.")
                self._no_state_logged = True
            return

        self._no_state_logged = False

    # 4) Direction voiture
        steer_raw = state.steering_from_gyro(sensitivity_deg_per_s=45.0)
        alpha = 0.3
        self._steer_filtered = (1 - alpha) * self._steer_filtered + alpha * steer_raw

        gain_px_per_sec = 400
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
        self.calib = HandCalibrator()
        # charge calibration.txt si elle existe
        try:
            self.calib.load_txt("calibration.txt")
        except Exception:
            pass

        sm = ScreenManager()
        sm.add_widget(CalibrationScreen(name="calibration"))
        sm.add_widget(MenuScreen(name="menu"))
        sm.add_widget(GameScreen(name="game")) # voiture
        sm.add_widget(PianoGameScreen(name="piano")) # piano
        sm.add_widget(JumpGameScreen(name="jump"))  # jump
        sm.add_widget(FollowUpScreen(name="followup"))
        sm.add_widget(WristFollowUpScreen(name="followup_wrist"))
        sm.add_widget(FlexFollowUpScreen(name="followup_flex"))
        sm.add_widget(PressureFollowUpScreen(name="followup_pressure"))


        return sm



if __name__ == "__main__":
    GantJeuApp().run()




