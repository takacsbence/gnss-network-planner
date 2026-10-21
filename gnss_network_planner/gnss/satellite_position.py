
import numpy as np

from dataclasses import dataclass

@dataclass
class SatellitePosition:

    gnss_id: str
    sv_id: int

    x: float
    y: float
    z: float

    @property
    def ecef(self):
        return np.array([
            self.x,
            self.y,
            self.z,
        ])

