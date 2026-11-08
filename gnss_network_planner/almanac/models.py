from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class AlmanacRecord:
    system: str
    prn: int

    week_number: int
    toa_s: float

    eccentricity: float
    inclination_rad: float
    omega0_rad: float
    omega_rad: float
    m0_rad: float
    omega_dot_rad_s: float
    sqrt_a_m12: float

    af0_s: float
    af1_s_s: float

    health: int

    source_epoch: datetime | None = None

    @property
    def sat_id(self) -> str:
        return f"{self.system}{self.prn:02d}"