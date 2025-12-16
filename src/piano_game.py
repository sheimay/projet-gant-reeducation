# piano_game.py

from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty, StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.core.audio import SoundLoader  # 🔊 pour les sons
from kivy.app import App


from serial_reader import SerialHandReader
from hand_state import HandState

import random

# Mets True quand tu voudras tester avec l'Arduino branché
USE_ARDUINO = True




# ---------- Utilitaires capteurs ----------

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
    app = App.get_running_app()
    calib = getattr(app, "calib", None)

    if calib is None:
        # fallback : ancien comportement
        index_norm = _norm(state.flex_index, vmin=300, vmax=800)
        majeur_norm = _norm(state.flex_thumb, vmin=300, vmax=800)
        seuil_i = seuil_m = 0.6
    else:
        index_norm = _norm(state.flex_index, calib.flex_index_min, calib.flex_index_max)
        majeur_norm = _norm(state.flex_thumb, calib.flex_thumb_min, calib.flex_thumb_max)
        seuil_i = getattr(calib, "index_threshold", 0.6)
        seuil_m = getattr(calib, "majeur_threshold", 0.6)

    # discrimination + dominance (évite double déclenchement)
    index_pressed = (index_norm > seuil_i) and (index_norm > majeur_norm)
    majeur_pressed = (majeur_norm > seuil_m) and (majeur_norm > index_norm)

    return index_pressed, majeur_pressed


# ---------- Écran du mini-jeu piano ----------

class PianoGameScreen(Screen):
    """
    Mini-jeu "Piano" tour par tour :

      - le jeu génère une séquence de "index" / "majeur"
      - pour chaque tour, un seul doigt est attendu
      - le patient a une fenêtre de temps pour fléchir le bon doigt
      - si réussi -> note validée + SON de piano
    """

    score = NumericProperty(0)             # nb de notes réussies
    expected_finger = StringProperty("index")  # "index" ou "majeur"

    # Pour l'affichage temps réel des doigts (si besoin dans l'UI)
    index_active = BooleanProperty(False)
    majeur_active = BooleanProperty(False)

    # Pour le clignement des badges INDEX / MAJEUR
    index_badge_visible = BooleanProperty(False)
    majeur_badge_visible = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if USE_ARDUINO:
            # ⚠️ adapte le port série à ton PC
            self.serial_reader = SerialHandReader(
                port="/dev/cu.usbmodem1201",
                baudrate=115200,
            )
        else:
            self.serial_reader = None

        # Séquence de doigts à jouer : ["index", "majeur", ...]
        self.sequence: list[str] = []
        self.current_step: int = 0

        # Gestion d'un "tour"
        self.note_window = 2.0      # durée max d'un tour (en secondes)
        self.note_timer = 0.0       # temps écoulé depuis le début du tour
        self.note_resolved = False  # True si tour déjà validé (ou raté)

        # Pour le clignement visuel
        self._badge_blink_timer = 0.0

        # Pour détecter des "taps" plus tard si besoin
        self._prev_index_pressed = False
        self._prev_majeur_pressed = False

        # 🔊 Chargement des sons (index / majeur)
        self.sound_index = SoundLoader.load("assets/note_index.wav")
        self.sound_majeur = SoundLoader.load("assets/note_majeur.wav")

        # Optionnel : régler un volume plus doux
        if self.sound_index:
            self.sound_index.volume = 0.8
        if self.sound_majeur:
            self.sound_majeur.volume = 0.8

    # ----- Cycle de vie de l'écran -----

    def on_pre_enter(self):
        """Appelé quand on arrive sur l'écran."""
        self.score = 0
        self.generate_new_sequence()
        self.current_step = 0
        self.start_new_note()

        if self.serial_reader is not None:
            self.serial_reader.start()

        Clock.schedule_interval(self.update_game, 1.0 / 60.0)

    def on_leave(self):
        """Appelé quand on quitte l'écran."""
        Clock.unschedule(self.update_game)

        if self.serial_reader is not None:
            self.serial_reader.stop()

    # ----- Gestion de la séquence / des tours -----

    def generate_new_sequence(self, length: int = 16):
        """Crée une nouvelle séquence aléatoire de 'index' / 'majeur'."""
        self.sequence = [random.choice(["index", "majeur"]) for _ in range(length)]
        self.current_step = 0

    def start_new_note(self):
        """
        Démarre un nouveau "tour" :
          - fixe le doigt attendu
          - réinitialise les timers
        """
        # Si on est au bout de la séquence, on en recrée une
        if not self.sequence or self.current_step >= len(self.sequence):
            self.generate_new_sequence()

        self.expected_finger = self.sequence[self.current_step]
        self.note_timer = 0.0
        self.note_resolved = False
        self._badge_blink_timer = 0.0

    def advance_to_next_note(self):
        """Passe à la note suivante dans la séquence."""
        self.current_step += 1
        self.start_new_note()

    def _play_success_sound(self):
        """Joue le son correspondant au doigt attendu."""
        if self.expected_finger == "index" and self.sound_index:
            # on stop avant play au cas où le son est déjà en cours
            self.sound_index.stop()
            self.sound_index.play()
        elif self.expected_finger == "majeur" and self.sound_majeur:
            self.sound_majeur.stop()
            self.sound_majeur.play()

    def validate_current_note(self):
        """Appelé quand le patient a fléchi le bon doigt dans la fenêtre de temps."""
        if self.note_resolved:
            return  # déjà traité

        self.note_resolved = True
        self.score += 1

        # 🔊 jouer le son correspondant
        self._play_success_sound()

        # on passe directement à la note suivante
        self.advance_to_next_note()

    def fail_current_note(self):
        """Temps écoulé: on ne passe PAS à la note suivante, on redonne la même note."""
        if self.note_resolved:
            return

        # (Optionnel) compteur d'erreurs si tu veux
        # self.misses += 1

        # On relance le même step: reset timers et clignotement
        self.note_timer = 0.0
        self.note_resolved = False
        self._badge_blink_timer = 0.0

    # ----- Boucle de jeu -----

    def update_game(self, dt: float):
        """Boucle appelée ~60 fois par seconde."""
        # --- Gestion du temps du tour ---
        self.note_timer += dt
        if self.note_timer >= self.note_window and not self.note_resolved:
            # temps écoulé -> note ratée
            self.fail_current_note()
            return

        # --- Clignement du badge du doigt attendu ---
        self._badge_blink_timer += dt
        blink_on = int(self._badge_blink_timer * 2) % 2 == 0  # ~2 fois par seconde

        if self.expected_finger == "index":
            self.index_badge_visible = blink_on
            self.majeur_badge_visible = False
        else:
            self.majeur_badge_visible = blink_on
            self.index_badge_visible = False

        # --- Mode sans Arduino : démo visuelle, pas de contrôle réel ---
        if self.serial_reader is None:
            return

        # --- Mode avec Arduino : lecture réelle du gant ---
        state = self.serial_reader.get_latest_state()
        if state is None:
            return

        index_pressed, majeur_pressed = detect_fingers_pressed(state)

        # états pour la partie visuelle
        self.index_active = index_pressed
        self.majeur_active = majeur_pressed

        # Vérifier si la note actuelle est réussie
        if not self.note_resolved:
            if self.expected_finger == "index" and index_pressed:
                self.validate_current_note()
            elif self.expected_finger == "majeur" and majeur_pressed:
                self.validate_current_note()

        # mémorisation (si plus tard tu veux détecter des "taps")
        self._prev_index_pressed = index_pressed
        self._prev_majeur_pressed = majeur_pressed
