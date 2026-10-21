from dataclasses import dataclass

import numpy as np


@dataclass
class Station:
    name: str
    lat_deg: float
    lon_deg: float
    h: float

    @property
    def llh(self):

        return np.array([
            np.radians(self.lat_deg),
            np.radians(self.lon_deg),
            self.h,
        ])