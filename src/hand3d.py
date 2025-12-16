from kivy.uix.widget import Widget
from kivy.properties import NumericProperty
from kivy.clock import Clock

from kivy.graphics import RenderContext, Mesh, Callback
from kivy.graphics.opengl import glEnable, glDisable, GL_DEPTH_TEST
from kivy.graphics.transformation import Matrix


# GLSL core (macOS): in/out + version
VERT_SHADER = """
#version 150

in vec3 vPosition;

uniform mat4 u_mv;
uniform mat4 u_proj;

void main() {
    gl_Position = u_proj * u_mv * vec4(vPosition, 1.0);
}
"""

FRAG_SHADER = """
#version 150

out vec4 fragColor;
uniform vec4 u_color;

void main() {
    fragColor = u_color;
}
"""


def cube_vertices(size=1.0):
    s = size / 2.0
    verts = [
        -s, -s, -s,   s, -s, -s,   s,  s, -s,  -s,  s, -s,
        -s, -s,  s,   s, -s,  s,   s,  s,  s,  -s,  s,  s,
    ]
    idx = [
        0, 1, 2,  2, 3, 0,
        4, 5, 6,  6, 7, 4,
        0, 4, 7,  7, 3, 0,
        1, 5, 6,  6, 2, 1,
        3, 2, 6,  6, 7, 3,
        0, 1, 5,  5, 4, 0,
    ]
    return verts, idx


class Hand3DView(Widget):
    wrist_yaw = NumericProperty(0.0)  # degrés

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.canvas = RenderContext()
        self._mesh = None

        # Compile/link shader + log si erreur
        try:
            self.canvas.shader.vs = VERT_SHADER
            self.canvas.shader.fs = FRAG_SHADER
        except Exception as e:
            print("SHADER ERROR:", e)
            try:
                print("SHADER LOG:\n", self.canvas.shader.get_log())
            except Exception:
                pass
            raise

        verts, idx = cube_vertices(size=1.0)

        with self.canvas:
            Callback(self._enable_depth)
            self._mesh = Mesh(
                vertices=verts,
                indices=idx,
                fmt=[("vPosition", 3, "float")],
                mode="triangles",
            )
            Callback(self._disable_depth)

        # Couleur “peau” claire
        self.canvas["u_color"] = (0.92, 0.88, 0.82, 1.0)

        self.bind(pos=self._update_matrices, size=self._update_matrices)
        self.bind(wrist_yaw=self._update_matrices)
        Clock.schedule_interval(lambda dt: setattr(self, "wrist_yaw", self.wrist_yaw + 30*dt), 1/60)

        Clock.schedule_once(lambda *_: self._update_matrices(), 0)

    def _enable_depth(self, *args):
        glEnable(GL_DEPTH_TEST)

    def _disable_depth(self, *args):
        glDisable(GL_DEPTH_TEST)

    def _update_matrices(self, *args):
        aspect = max(1e-3, self.width / float(self.height if self.height else 1))
        proj = Matrix().perspective(45.0, aspect, 0.1, 100.0)

        mv = Matrix().identity()
        mv = mv.translate(0, 0, -3.0)
        mv = mv.rotate(-0.5, 1, 0, 0)  # tilt
        mv = mv.rotate(self.wrist_yaw * 0.01745329252, 0, 0, 1)
        mv = mv.scale(1.4, 1.4, 1.4)

        self.canvas["u_proj"] = proj
        self.canvas["u_mv"] = mv

