
from dataclasses import dataclass

@dataclass
class SatellitePosition:

    gnss_id: str
    sv_id: int

    x: float
    y: float
    z: float


