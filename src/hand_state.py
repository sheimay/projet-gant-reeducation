from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class HandState:
    t_ms: int
    flex_thumb: int
    flex_index: int
    fsr_thumb: int
    fsr_index: int
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float

    @staticmethod
    def from_csv_line(line: str) -> Optional["HandState"]:
        """
        Parse une ligne CSV du type :
        t_ms,flex_thumb,flex_index,fsr_thumb,fsr_index,ax,ay,az,gx,gy,gz
        et renvoie un HandState, ou None si la ligne est invalide.
        """
        line = line.strip()
        if not line:
            return None

        # Ignorer une éventuelle ligne d'en-tête
        if line.startswith("t_ms"):
            return None

        parts: List[str] = line.split(",")
        if len(parts) != 11:
            # Ligne pas au bon format -> on ignore
            return None

        try:
            return HandState(
                t_ms=int(parts[0]),
                flex_thumb=int(parts[1]),
                flex_index=int(parts[2]),
                fsr_thumb=int(parts[3]),
                fsr_index=int(parts[4]),
                ax=float(parts[5]),
                ay=float(parts[6]),
                az=float(parts[7]),
                gx=float(parts[8]),
                gy=float(parts[9]),
                gz=float(parts[10]),
            )
        except ValueError:
            # Une des valeurs ne se convertit pas -> on ignore
            return None

    def steering_from_gyro(self, sensitivity_deg_per_s: float = 90.0) -> float:
        """
        Calcule une commande de direction à partir du gyroscope.
        On utilise gz (vitesse angulaire autour de l'axe Z, en deg/s).
        Retourne une valeur dans [-1, 1] :
          -1 = plein gauche, +1 = plein droite, 0 = neutre.
        """
        raw = self.gx / sensitivity_deg_per_s
        if raw < -1.0:
            raw = -1.0
        if raw > 1.0:
            raw = 1.0
        return raw


class HandCalibrator:
    """
    Gère les min/max pour normaliser les valeurs des capteurs en [0, 1].
    (utile si tu veux exploiter flexion + FSR).
    """

    def __init__(self):
        self.flex_thumb_min = 200
        self.flex_thumb_max = 800
        self.flex_index_min = 200
        self.flex_index_max = 800
        self.fsr_thumb_min = 50
        self.fsr_thumb_max = 900
        self.fsr_index_min = 50
        self.fsr_index_max = 900

        # --- OFFSETS "repos" (calibration) ---
        self.flex_thumb_rest = 0.0
        self.flex_index_rest = 0.0
        self.fsr_thumb_rest = 0.0
        self.fsr_index_rest = 0.0
        self.gx_offset = 0.0
        self.gy_offset = 0.0
        self.gz_offset = 0.0

        def save_txt(self, path: str):
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"flex_thumb_rest={self.flex_thumb_rest}\n")
                f.write(f"flex_index_rest={self.flex_index_rest}\n")
                f.write(f"fsr_thumb_rest={self.fsr_thumb_rest}\n")
                f.write(f"fsr_index_rest={self.fsr_index_rest}\n")
                f.write(f"gx_offset={self.gx_offset}\n")
                f.write(f"gy_offset={self.gy_offset}\n")
                f.write(f"gz_offset={self.gz_offset}\n")

        def load_txt(self, path: str) -> bool:
            try:
                data = {}
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        data[k.strip()] = float(v.strip())

                self.flex_thumb_rest = data.get("flex_thumb_rest", self.flex_thumb_rest)
                self.flex_index_rest = data.get("flex_index_rest", self.flex_index_rest)
                self.fsr_thumb_rest = data.get("fsr_thumb_rest", self.fsr_thumb_rest)
                self.fsr_index_rest = data.get("fsr_index_rest", self.fsr_index_rest)
                self.gx_offset = data.get("gx_offset", self.gx_offset)
                self.gy_offset = data.get("gy_offset", self.gy_offset)
                self.gz_offset = data.get("gz_offset", self.gz_offset)
                return True
            except Exception:
                return False


    @staticmethod
    def _norm(self, vmin: float, vmax: float) -> float:
        if vmax <= vmin:
            return 0.0
        x = (self - vmin) / (vmax - vmin)
        if x < 0.0:
            x = 0.0
        if x > 1.0:
            x = 1.0
        return x

    def normalize_flex_thumb(self, v: float) -> float:
        return self._norm(v, self.flex_thumb_min, self.flex_thumb_max)

    def normalize_flex_index(self, v: float) -> float:
        return self._norm(v, self.flex_index_min, self.flex_index_max)

    def normalize_fsr_thumb(self, v: float) -> float:
        return self._norm(v, self.fsr_thumb_min, self.fsr_thumb_max)

    def normalize_fsr_index(self, v: float) -> float:
        return self._norm(v, self.fsr_index_min, self.fsr_index_max)
