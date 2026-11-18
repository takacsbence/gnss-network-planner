from datetime import datetime, timedelta, timezone

# GPS time reference epoch (1980-01-06 00:00:00 UTC).
GPS_EPOCH = datetime(
    1980,
    1,
    6,
    tzinfo=timezone.utc,
)


def gps_time_to_datetime(
    week: int,
    tow: float,
) -> datetime:
    """
    Convert GPS week and time-of-week to UTC datetime.

    Parameters
    ----------
    week : int
        GPS week number.
    tow : float
        GPS time-of-week [s].

    Returns
    -------
    datetime
        Corresponding UTC datetime.
    """
    return GPS_EPOCH + timedelta(
        weeks=week,
        seconds=tow,
    )


# GPS-UTC offset valid since 2017.
# May be overridden by MGA-INI-TIME-UTC information if available.
LEAP_GPS_UTC = 18

# Difference between GPST and BeiDou Time (BDT) in seconds.
BDT_GPST = 14

# Week numbering offsets relative to GPS week numbers.
BDS_WEEK_OFFSET = 1356
GST_WEEK_OFFSET = 1024


def datetime_to_gps_time(
    t_utc: datetime,
    leap: int,
) -> tuple[int, float]:
    """
    Convert UTC datetime to GPS week and time-of-week.

    Parameters
    ----------
    t_utc : datetime
        UTC epoch.
    leap : int
        GPS-UTC offset in seconds.

    Returns
    -------
    tuple[int, float]
        GPS week and GPS time-of-week [s].
    """

    s = (
        t_utc - GPS_EPOCH
    ).total_seconds() + leap

    week = int(s // 604800)
    tow = s - week * 604800

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

    full_week = (
        current_week
        - ((current_week - truncated_week) % modulus)
    )

    if current_week - full_week > modulus // 2:
        full_week += modulus

    return full_week