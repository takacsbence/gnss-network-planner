from datetime import datetime, timedelta, timezone

"""
GPS epoch represented as a timezone-aware datetime.

IMPORTANT:
The datetime value is interpreted on the GPS timescale.
The UTC timezone is used only to keep datetime objects aware.
No leap-second correction is applied anywhere in the project.
"""

GPS_EPOCH = datetime(
    1980,
    1,
    6,
    tzinfo=timezone.utc,
)

SECONDS_PER_WEEK = 604800

def gps_time_to_datetime(
    week: int,
    tow: float,
) -> datetime:
    """
    Convert GPS week and time-of-week to a GPS datetime.

    Notes
    -----
    The returned datetime is timezone-aware and uses UTC tzinfo.
    However, the datetime value itself is interpreted on the GPS timescale.
    No GPS-UTC conversion is performed.

    Parameters
    ----------
    week : int
        GPS week number.
    tow : float
        GPS time-of-week [s].

    Returns
    -------
    datetime
        GPS datetime.
    """
    return GPS_EPOCH + timedelta(
        weeks=week,
        seconds=tow,
    )

# BDT lags GPST by 14 seconds.
BDT_GPST_OFFSET = 14

# Week numbering offsets relative to GPS week numbers.
BDS_WEEK_OFFSET = 1356
GST_WEEK_OFFSET = 1024

def datetime_to_gps_time(
    t_gps: datetime,
) -> tuple[int, float]:
    """
    Convert a GPS datetime to GPS week and time-of-week.

    Notes
    -----
    The returned datetime is timezone-aware and uses UTC tzinfo.
    However, the datetime value itself is interpreted on the GPS timescale.
    No GPS-UTC conversion is performed.

    Parameters
    ----------
    t_gps : datetime
        GPS datetime.

    Returns
    -------
    tuple[int, float]
        GPS week and GPS time-of-week [s].
    """

    s = (t_gps - GPS_EPOCH).total_seconds()

    week = int(s // SECONDS_PER_WEEK)
    tow = s - week * SECONDS_PER_WEEK

    return week, tow

def resolve_full_week(
    current_week: int,
    truncated_week: int,
    modulus: int,
) -> int:
    """
    Reconstruct the full week number from a truncated almanac week.

    The full week closest to the current week is selected.
    This handles GNSS almanac week rollovers.

    Parameters
    ----------
    current_week : int
        Current GNSS week number.
    truncated_week : int
        Week number transmitted in the almanac.
    modulus : int
        Almanac rollover period (e.g. 256 or 1024 weeks).

    Returns
    -------
    int
        Reconstructed full week number.
    """

    # Candidate week having the same truncated representation.
    full_week = (
        current_week
        - ((current_week - truncated_week) % modulus)
    )

    if current_week - full_week > modulus // 2:
        full_week += modulus

    return full_week