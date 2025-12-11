# piano_game.py

from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty, StringProperty, BooleanProperty
from kivy.clock import Clock

from serial_reader import SerialHandReader
from hand_state import HandState

import random

# Mets False pour tester l'interface sans Arduino branché
USE_ARDUINO = False


def _norm(value, vmin, vmax):
    """Normalise value entre 0 et 1 avec saturation."""
    if vmax <= vmin:
        return 0.0
    x = (value - vmin) / float(vmax - vmin)
    if x < 0.0:
        x = 0.0
    if x > 1.0:
        x = 1.0
    return x


def detect_fingers_pressed(state: HandState):
    """
    Retourne (index_pressed, majeur_pressed) à partir de HandState.

    Hypothèse actuelle :
      - state.flex_index = capteur sur INDEX
      - state.flex_thumb = capteur sur MAJEUR
    Tu pourras adapter quand tu auras branché les capteurs.
    """
    # TODO : ajuste ces min/max après avoir observé tes vraies valeurs
    index_norm = _norm(state.flex_index, vmin=300, vmax=800)
    majeur_norm = _norm(state.flex_thumb, vmin=300, vmax=800)

    seuil = 0.6  # au-dessus de 0.6 = doigt bien fléchi

    index_pressed = index_norm > seuil
    majeur_pressed = majeur_norm > seuil

    return index_pressed, majeur_pressed


class PianoGameScreen(Screen):
    """
    Mini-jeu "Piano" :
      - le jeu affiche une séquence de doigts à jouer ("index" / "majeur")
      - le patient doit plier le bon doigt
    """
    score = NumericProperty(0)
    expected_finger = StringProperty("index")  # "index" ou "majeur"

    # pour l’affichage des touches (allumées / éteintes)
    index_active = BooleanProperty(False)
    majeur_active = BooleanProperty(False)
    
    # ✅ visibilité/clignement des badges de légende
    index_badge_visible = BooleanProperty(False)
    majeur_badge_visible = BooleanProperty(False)


    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if USE_ARDUINO:
            # ⚠️ mets ici le bon port quand tu testeras avec le gant
            self.serial_reader = SerialHandReader(
                port="COM3",   # ex: "COM4" ou autre selon ton PC
                baudrate=115200,
            )
        else:
            # mode sans Arduino : pas de lecteur série
            self.serial_reader = None

        self._prev_index_pressed = False
        self._prev_majeur_pressed = False

        self.sequence = []      # liste de "index" / "majeur"
        self.current_step = 0   # index de la note actuelle
        self._debug_time = 0.0  # pour l’animation en mode sans Arduino

                # Timers pour le clignement / alternance des badges
        self._badge_timer = 0.0      # pour le clignement rapide
        self._sequence_timer = 0.0   # pour changer de doigt toutes les 5 s
        self._current_badge = "index"

    # -------- Cycle de vie de l'écran --------

    def on_pre_enter(self):
        """Appelé automatiquement quand on arrive sur l'écran 'piano'."""
        self.score = 0
        self.generate_new_sequence()

        # ✅ état initial des badges
        self._badge_timer = 0.0
        self._sequence_timer = 0.0
        self._current_badge = "index"
        self.index_badge_visible = True
        self.majeur_badge_visible = False
        self.generate_new_sequence()

        if self.serial_reader is not None:
            self.serial_reader.start()

        Clock.schedule_interval(self.update_game, 1.0 / 60.0)

    def on_leave(self):
        """Appelé automatiquement quand on quitte l'écran 'piano'."""
        Clock.unschedule(self.update_game)

        if self.serial_reader is not None:
            self.serial_reader.stop()

    # -------- Logique du jeu --------

    def generate_new_sequence(self, length=8):
        """Génère une nouvelle séquence pseudo-aléatoire de doigts."""
        self.sequence = [random.choice(["index", "majeur"]) for _ in range(length)]
        self.current_step = 0
        if self.sequence:
            self.expected_finger = self.sequence[0]
        else:
            self.expected_finger = "index"

    def update_game(self, dt):
        """Boucle de jeu appelée ~60 fois par seconde."""
        # --- Gestion du clignement des badges (indication de flexion) ---
        self._badge_timer += dt
        self._sequence_timer += dt

        # clignement rapide (~2 fois par seconde)
        blink_on = int(self._badge_timer * 2) % 2 == 0

        if self._current_badge == "index":
            self.index_badge_visible = blink_on
            self.majeur_badge_visible = False
        else:
            self.majeur_badge_visible = blink_on
            self.index_badge_visible = False

        # changement de doigt toutes les 5 secondes
        if self._sequence_timer >= 5.0:
            self._sequence_timer = 0.0
            self._current_badge = "majeur" if self._current_badge == "index" else "index"

        # (optionnel) aligner la logique de jeu sur le doigt attendu
        self.expected_finger = self._current_badge


        # --- MODE SANS ARDUINO : juste pour tester l'UI ---
        if self.serial_reader is None:
            self._debug_time += dt
            # alterne toutes les 0.5 secondes
            blink = int(self._debug_time * 2) % 2 == 0
            self.index_active = blink
            self.majeur_active = not blink
            return

        # --- MODE AVEC ARDUINO ---
        state = self.serial_reader.get_latest_state()
        if state is None:
            return

        index_pressed, majeur_pressed = detect_fingers_pressed(state)

        # mise à jour visuelle
        self.index_active = index_pressed
        self.majeur_active = majeur_pressed

        # détection d'un "tap" = passage relâché -> pressé
        new_index_tap = index_pressed and not self._prev_index_pressed
        new_majeur_tap = majeur_pressed and not self._prev_majeur_pressed

        if new_index_tap:
            self.handle_finger_tap("index")
        if new_majeur_tap:
            self.handle_finger_tap("majeur")

        self._prev_index_pressed = index_pressed
        self._prev_majeur_pressed = majeur_pressed

    def handle_finger_tap(self, finger):
        """Appelé quand un doigt vient de se fléchir (tap)."""
        if not self.sequence:
            return

        expected = self.sequence[self.current_step]

        if finger == expected:
            # ✅ Bon doigt
            self.score += 1
            self.current_step += 1

            if self.current_step >= len(self.sequence):
                # Séquence terminée -> nouvelle séquence
                self.generate_new_sequence()
            else:
                self.expected_finger = self.sequence[self.current_step]
        else:
            # ❌ Mauvais doigt : tu pourras ajouter plus tard un feedback spécial
            pass
