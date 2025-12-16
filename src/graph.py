from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty
from kivy.clock import Clock
from kivy.app import App

from collections import deque

from serial_reader import SerialHandReader
from kivy_garden.graph import Graph, LinePlot


USE_ARDUINO = True
SERIAL_PORT = "/dev/cu.usbmodem1201"
SERIAL_BAUD = 115200


class WristFollowUpScreen(Screen):
    """
    Écran de suivi : rotation du poignet
    Graphe angle (°) en fonction du temps
    """

    # attribut de classe (important pour Kivy)
    window_s = 10.0
    current_angle = NumericProperty(0.0)
    current_rate = NumericProperty(0.0)   # deg/s


    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.serial_reader = None
        self._event = None

        self._t = 0.0
        self._angle_deg = 0.0
        self._samples = deque()

        self.graph = None
        self.plot = None

    # --------------------------------------------------
    # Création du graphe (appelé une seule fois)
    # --------------------------------------------------
    def _ensure_graph(self):
        if self.graph is not None:
            return

        self.graph = Graph(
            xlabel="t (s)",
            ylabel="angle (°)",
            xmin=0,
            xmax=self.window_s,
            ymin=-180,
            ymax=180,
            x_ticks_major=1,
            x_ticks_minor=5,
            y_ticks_major=30,
            x_grid=True,
            y_grid=True,
            padding=8,
            background_color=(1, 1, 1, 1),          # fond blanc
            border_color=(0.8, 0.8, 0.8, 1),
            tick_color=(0.6, 0.6, 0.6, 1),
            label_options={"color": (0.35, 0.35, 0.35, 1)},
        )

        self.plot = LinePlot(
            line_width=2,
            color=(0.55, 0.75, 0.95, 1)   # bleu pastel
        )

        self.graph.add_plot(self.plot)
        self.ids.graph_container.clear_widgets()
        self.ids.graph_container.add_widget(self.graph)

    # --------------------------------------------------
    # Lifecycle écran
    # --------------------------------------------------
    def on_pre_enter(self):
        self._t = 0.0
        self._angle_deg = 0.0
        self._samples.clear()

        self._ensure_graph()

        if USE_ARDUINO:
            self.serial_reader = SerialHandReader(
                port=SERIAL_PORT,
                baudrate=SERIAL_BAUD
            )
            self.serial_reader.start()

        self._event = Clock.schedule_interval(self._update, 1.0 / 30.0)

    def on_leave(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None

        if self.serial_reader is not None:
            self.serial_reader.stop()
            self.serial_reader = None

    # --------------------------------------------------
    # Update graphe
    # --------------------------------------------------
    def _update(self, dt: float):
        if self.plot is None or self.serial_reader is None:
            return

        self._t += dt

        state = self.serial_reader.get_latest_state()
        if state is None:
            return

        calib = getattr(App.get_running_app(), "calib", None)
        gx_offset = getattr(calib, "gx_offset", 0.0) if calib else 0.0

        gx_deg_s = state.gx - gx_offset
        self._angle_deg += gx_deg_s * dt

        self.current_rate = float(gx_deg_s)
        self.current_angle = float(self._angle_deg)

        if "hand3d" in self.ids:
            self.ids.hand3d.wrist_yaw = self.current_angle


        # Limiter pour lisibilité
        if self._angle_deg > 180:
            self._angle_deg -= 360
        elif self._angle_deg < -180:
            self._angle_deg += 360

        self._samples.append((self._t, self._angle_deg))
        while self._samples and (self._t - self._samples[0][0]) > self.window_s:
            self._samples.popleft()

        t0 = self._samples[0][0] if self._samples else self._t
        self.plot.points = [(t - t0, a) for (t, a) in self._samples]
        

def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def _norm(value: float, vmin: float, vmax: float) -> float:
    if vmax <= vmin:
        return 0.0
    return _clamp01((value - vmin) / float(vmax - vmin))


class FlexFollowUpScreen(Screen):
    """Suivi flexion: 2 courbes (index, majeur)."""

    window_s = 10.0
    current_index = NumericProperty(0.0)   # 0..1
    current_majeur = NumericProperty(0.0)  # 0..1


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.serial_reader = None
        self._event = None
        self._t = 0.0
        self._samples = deque()

        self.graph = None
        self.plot_index = None
        self.plot_majeur = None

    def _ensure_graph(self):
        if self.graph is not None:
            return

        self.graph = Graph(
            xlabel="t (s)",
            ylabel="flexion (0..1)",
            xmin=0, xmax=self.window_s,
            ymin=0, ymax=1,
            x_ticks_major=1, x_ticks_minor=5,
            y_ticks_major=0.2,
            x_grid=True, y_grid=True,
            padding=8,
            background_color=(1, 1, 1, 1),
            border_color=(0.8, 0.8, 0.8, 1),
            tick_color=(0.6, 0.6, 0.6, 1),
            label_options={"color": (0.35, 0.35, 0.35, 1)},
        )

        # Pastels
        self.plot_index = LinePlot(line_width=2, color=(0.55, 0.75, 0.95, 1))   # bleu pastel
        self.plot_majeur = LinePlot(line_width=2, color=(0.78, 0.72, 0.92, 1))  # violet pastel

        self.graph.add_plot(self.plot_index)
        self.graph.add_plot(self.plot_majeur)

        self.ids.graph_container.clear_widgets()
        self.ids.graph_container.add_widget(self.graph)

    def on_pre_enter(self):
        self._t = 0.0
        self._samples.clear()
        self._ensure_graph()

        if USE_ARDUINO:
            self.serial_reader = SerialHandReader(port=SERIAL_PORT, baudrate=SERIAL_BAUD)
            self.serial_reader.start()

        self._event = Clock.schedule_interval(self._update, 1.0 / 30.0)

    def on_leave(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None
        if self.serial_reader is not None:
            self.serial_reader.stop()
            self.serial_reader = None

    def _update(self, dt: float):
        if self.serial_reader is None or self.plot_index is None or self.plot_majeur is None:
            return

        self._t += dt
        state = self.serial_reader.get_latest_state()
        if state is None:
            return

        calib = getattr(App.get_running_app(), "calib", None)

        # ⚠️ Assure-toi que HandState a bien flex_index et flex_majeur
        if calib:
            index_n = _norm(state.flex_index, calib.flex_index_min, calib.flex_index_max)
            majeur_n = _norm(state.flex_thumb, calib.flex_thumb_min, calib.flex_thumb_max)
        else:
            index_n = _clamp01(state.flex_index / 1023.0)
            majeur_n = _clamp01(state.flex_thumb / 1023.0)


        self.current_index = float(index_n)
        self.current_majeur = float(majeur_n)

        if "hand3d" in self.ids:
            self.ids.hand3d.flex_index = self.current_index
            self.ids.hand3d.flex_index = 0.5



        self._samples.append((self._t, index_n, majeur_n))
        while self._samples and (self._t - self._samples[0][0]) > self.window_s:
            self._samples.popleft()

        t0 = self._samples[0][0]
        self.plot_index.points = [(t - t0, i) for (t, i, m) in self._samples]
        self.plot_majeur.points = [(t - t0, m) for (t, i, m) in self._samples]
   

class PressureFollowUpScreen(Screen):
    """Suivi pression: 1 courbe (FSR index)."""

    window_s = 10.0
    current_pressure = NumericProperty(0.0)  # 0..1


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.serial_reader = None
        self._event = None
        self._t = 0.0
        self._samples = deque()

        self.graph = None
        self.plot_pressure = None

    def _ensure_graph(self):
        if self.graph is not None:
            return

        self.graph = Graph(
            xlabel="t (s)",
            ylabel="pression (0..1)",
            xmin=0, xmax=self.window_s,
            ymin=0, ymax=1,
            x_ticks_major=1, x_ticks_minor=5,
            y_ticks_major=0.2,
            x_grid=True, y_grid=True,
            padding=8,
            background_color=(1, 1, 1, 1),
            border_color=(0.8, 0.8, 0.8, 1),
            tick_color=(0.6, 0.6, 0.6, 1),
            label_options={"color": (0.35, 0.35, 0.35, 1)},
        )

        # Pastel vert
        self.plot_pressure = LinePlot(line_width=2, color=(0.70, 0.85, 0.70, 1))

        self.graph.add_plot(self.plot_pressure)

        self.ids.graph_container.clear_widgets()
        self.ids.graph_container.add_widget(self.graph)

    def on_pre_enter(self):
        self._t = 0.0
        self._samples.clear()
        self._ensure_graph()

        if USE_ARDUINO:
            self.serial_reader = SerialHandReader(port=SERIAL_PORT, baudrate=SERIAL_BAUD)
            self.serial_reader.start()

        self._event = Clock.schedule_interval(self._update, 1.0 / 30.0)

    def on_leave(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None
        if self.serial_reader is not None:
            self.serial_reader.stop()
            self.serial_reader = None

    def _update(self, dt: float):
        if self.serial_reader is None or self.plot_pressure is None:
            return

        self._t += dt
        state = self.serial_reader.get_latest_state()
        if state is None:
            return

        calib = getattr(App.get_running_app(), "calib", None)

        if calib:
            p_n = _norm(state.fsr_index, calib.fsr_index_min, calib.fsr_index_max)
        else:
            p_n = _clamp01(state.fsr_index / 1023.0)

        self.current_pressure = float(p_n)


        self._samples.append((self._t, p_n))
        while self._samples and (self._t - self._samples[0][0]) > self.window_s:
            self._samples.popleft()

        t0 = self._samples[0][0]
        self.plot_pressure.points = [(t - t0, p) for (t, p) in self._samples]