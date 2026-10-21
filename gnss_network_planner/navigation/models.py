from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

@dataclass
class TimeSystemCorrection:
    """
    RINEX time system correction parameters.

    Describes the offset and drift between two GNSS time systems
    as provided by the TIME SYSTEM CORR records in the RINEX
    navigation file header.

    Examples:
        GPGA : GPS to Galileo time correction
        GAUT : Galileo to UTC correction
        QZUT : QZSS to UTC correction
    """
    system: str
    a0: float
    a1: float
    reference_time: Optional[float] = None
    reference_week: Optional[int] = None

@dataclass
class IonosphericCorrection:
    """
    Broadcast ionospheric model parameters.

    Stores ionospheric correction coefficients extracted from the
    RINEX navigation file header. The interpretation of the
    coefficients depends on the GNSS and correction type.

    Examples:
        GPSA / GPSB : GPS Klobuchar coefficients
        BDSA / BDSB : BeiDou ionospheric parameters
        GAL         : Galileo ionospheric parameters
    """
    system: str
    correction_type: str
    coefficients: tuple[float, ...]

@dataclass
class RinexNavHeader:
    """
    Parsed RINEX navigation file header.

    Contains all metadata extracted from the header section of
    a RINEX navigation file, including file identification,
    processing software information, comments, time system
    corrections, ionospheric model parameters and leap-second
    information.

    This object is stored together with the navigation records
    in a RinexNavigationFile instance.
    """
    version: float
    file_type: str
    system: Optional[str] = None

    program: Optional[str] = None
    run_by: Optional[str] = None
    date: Optional[str] = None

    comments: list[str] = field(default_factory=list)

    time_system_corrections: list[TimeSystemCorrection] = field(
        default_factory=list
    )
    ionospheric_corrections: list[IonosphericCorrection] = field(
        default_factory=list
    )

    leap_seconds: Optional[int] = None

@dataclass
class BroadcastEphemeris:
    """
    Unified representation of a single RINEX navigation record.

    This class stores all broadcast ephemeris parameters parsed
    from a RINEX navigation file. It supports GPS, Galileo,
    BeiDou, QZSS, NavIC and GLONASS records using a common model.

    Parameters that are not applicable to a specific GNSS are
    set to None.
    """

    # ------------------------------------------------------------------
    # Satellite identification
    # ------------------------------------------------------------------
    gnss_id: str
    sv_id: int

    # ------------------------------------------------------------------
    # Time tags
    # ------------------------------------------------------------------
    epoch: datetime
    time: datetime

    gps_week: Optional[int] = None
    gps_tow: Optional[float] = None

    # ------------------------------------------------------------------
    # Satellite clock correction parameters
    # ------------------------------------------------------------------
    af0: Optional[float] = None
    af1: Optional[float] = None
    af2: Optional[float] = None

    # ------------------------------------------------------------------
    # Keplerian orbit parameters
    # ------------------------------------------------------------------
    sqrt_a: Optional[float] = None
    e: Optional[float] = None
    m0: Optional[float] = None

    delta_n: Optional[float] = None

    omega: Optional[float] = None
    omega0: Optional[float] = None
    omega_dot: Optional[float] = None

    i0: Optional[float] = None
    idot: Optional[float] = None

    cuc: Optional[float] = None
    cus: Optional[float] = None
    crc: Optional[float] = None
    crs: Optional[float] = None
    cic: Optional[float] = None
    cis: Optional[float] = None

    toe: Optional[float] = None
    toc: Optional[float] = None

    # ------------------------------------------------------------------
    # GPS-specific parameters
    # ------------------------------------------------------------------
    tgd: Optional[float] = None

    iodc: Optional[int] = None
    iode: Optional[int] = None

    # ------------------------------------------------------------------
    # Galileo-specific parameters
    # ------------------------------------------------------------------
    bgd_e1_e5a: Optional[float] = None
    bgd_e1_e5b: Optional[float] = None

    # ------------------------------------------------------------------
    # BeiDou-specific parameters
    # ------------------------------------------------------------------
    tgd1: Optional[float] = None
    tgd2: Optional[float] = None

    # ------------------------------------------------------------------
    # GLONASS state vector parameters
    # ------------------------------------------------------------------
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None

    vx: Optional[float] = None
    vy: Optional[float] = None
    vz: Optional[float] = None

    ax: Optional[float] = None
    ay: Optional[float] = None
    az: Optional[float] = None

    gamma: Optional[float] = None
    tau_n: Optional[float] = None
    tau_c: Optional[float] = None

    freq_channel: Optional[int] = None

    # ------------------------------------------------------------------
    # Quality and health information
    # ------------------------------------------------------------------
    ura: Optional[float] = None
    health: Optional[int] = None

    def __post_init__(self):
        for name in ("epoch", "time"):
            dt = getattr(self, name)

            if dt.tzinfo is None:
                raise ValueError(
                    f"{name} must be timezone-aware"
                )

            if dt.tzinfo != timezone.utc:
                raise ValueError(
                    f"{name} must be UTC"
                )

    @property
    def constellation(self) -> str:
        """
        GNSS constellation identifier
        (G, R, E, C, J, I, ...).
        """
        return self.gnss_id

    @property
    def prn(self) -> int:
        """
        Satellite PRN number within the constellation.
        """
        return self.sv_id

@dataclass
class RinexNavigationFile:
    """
    Complete contents of a RINEX navigation file.

    Contains the parsed file header and all navigation
    records contained in the file.
    """
    header: RinexNavHeader
    records: list[BroadcastEphemeris] = field(default_factory=list)