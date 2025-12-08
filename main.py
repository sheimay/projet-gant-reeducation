from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import NumericProperty
from kivy.core.window import Window
from kivy.clock import Clock

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
        self.forward_speed = 200  # px/s

    def on_kv_post(self, base_widget):
        self.car_x = self.width / 2
        self.scroll_y = 0
        self.distance = 0

    def on_pre_enter(self, *args):
        print(">>> ON ENTRE DANS GameScreen")  # DEBUG
        Window.bind(on_key_down=self.on_key_down)
        self._update_event = Clock.schedule_interval(self.update_game, 1 / 60)

    def on_leave(self, *args):
        Window.unbind(on_key_down=self.on_key_down)
        if self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None

    def on_size(self, *args):
        self.car_x = self.width / 2

    def on_key_down(self, window, key, scancode, codepoint, modifiers):
        if key == 276:      # gauche
            self.move_car_delta(-0.2)
        elif key == 275:    # droite
            self.move_car_delta(0.2)

    def move_car_delta(self, delta_norm: float):
        self.car_x += delta_norm * self.width * 0.05
        self._clamp_car()

    def update_game(self, dt):
        if self.height > 0:
            self.scroll_y -= self.forward_speed * dt
            if self.scroll_y <= -self.height:
                self.scroll_y += self.height

        self.distance += (self.forward_speed * dt) / 100.0

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
