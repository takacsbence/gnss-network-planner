from dataclasses import dataclass


@dataclass
class Station:
    name: str
    lat_deg: float
    lon_deg: float
    h: float