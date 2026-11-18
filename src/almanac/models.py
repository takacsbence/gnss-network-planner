from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class AlmanacRecord:
    """
    Unified representation of a single broadcast almanac record.

    Parameters are stored using the same naming conventions
    and units as BroadcastEphemeris whenever possible.
    """

    # ------------------------------------------------------------------
    # Satellite identification
    # ------------------------------------------------------------------
    gnss_id: str
    sv_id: int

    # ------------------------------------------------------------------
    # Time tags
    # ------------------------------------------------------------------
    week: int | None = None
    toa: float | None = None

    source_epoch: datetime | None = None

    # ------------------------------------------------------------------
    # Satellite clock correction parameters
    # ------------------------------------------------------------------
    af0: float = 0.0
    af1: float = 0.0

    # ------------------------------------------------------------------
    # Keplerian orbit parameters
    # ------------------------------------------------------------------
    sqrt_a: float = 0.0
    e: float = 0.0
    m0: float = 0.0

    omega: float = 0.0
    omega0: float = 0.0
    omega_dot: float = 0.0

    i0: float = 0.0

    # --------------------------------------------------------------
    # GLONASS-specific almanac parameters
    # --------------------------------------------------------------
    glonass_n: int | None = None
    glonass_m: int | None = None
    glonass_h: int | None = None

    tau: float | None = None
    lam: float | None = None
    di: float | None = None

    tlam: float | None = None

    dT: float | None = None
    dTdot: float | None = None

    # ------------------------------------------------------------------
    # Quality and health information
    # ------------------------------------------------------------------
    health: int = 0

    def __post_init__(self) -> None:
        if self.source_epoch is not None:
            if self.source_epoch.tzinfo is None:
                raise ValueError(
                    "source_epoch must be timezone-aware"
                )

            if self.source_epoch.tzinfo != timezone.utc:
                raise ValueError(
                    "source_epoch must be UTC"
                )

    # ------------------------------------------------------------------
    # others
    # ------------------------------------------------------------------
    is_geo: bool | None = None

    @property
    def constellation(self) -> str:
        """GNSS constellation identifier."""
        return self.gnss_id

    @property
    def prn(self) -> int:
        """Satellite PRN number."""
        return self.sv_id

    @property
    def sat_id(self) -> str:
        """Formatted satellite identifier."""
        return f"{self.gnss_id}{self.sv_id:02d}"