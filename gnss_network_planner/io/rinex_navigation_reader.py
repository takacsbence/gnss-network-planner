"""
RINEX Navigation File Parser.

This module implements a lightweight parser for RINEX 3 and
RINEX 4 navigation files and converts the broadcast navigation
messages into NavigationData objects.

Supported constellations:
    - GPS (G)
    - GLONASS (R)
    - Galileo (E)
    - BeiDou (C)
    - QZSS (J)
    - NavIC / IRNSS (I)

The parser provides:
    - Header parsing
    - Time system corrections
    - Ionospheric corrections
    - Broadcast ephemeris records
    - GLONASS state vector records

The resulting data structures are intended to populate the
EphemerisDatabase used by the SPP/PPP processing chain.
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path

from gnss_network_planner.navigation.models import (
    TimeSystemCorrection,
    IonosphericCorrection,
    RinexNavHeader,
    BroadcastEphemeris,
    RinexNavigationFile,
)

GPS_EPOCH = datetime(
    1980,
    1,
    6,
    tzinfo=timezone.utc,
)
# ============================================================================
# LOW LEVEL HELPERS
# ============================================================================
def _float(value: str) -> Optional[float]:
    """
    Parse a RINEX floating-point field.

    RINEX navigation files may use either E or D
    exponential notation. Invalid or empty fields
    return None.
    """
    value = value.strip()
    if not value:
        return None

    try:
        return float(value.replace("D", "E").replace("d", "e"))
    except ValueError:
        return None

def _int(value: str) -> Optional:
    """
    Parse an integer field.

    Some RINEX records store integer values using
    floating-point notation. This helper handles
    both formats.
    """

    value = value.strip()
    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        try:
            return int(float(value.replace("D", "E").replace("d", "e")))
        except ValueError:
            return None


def _fields(line: str) -> list[Optional[float]]:
    """
    Parse one navigation data line.

    Each continuation line contains four fixed-width
    floating-point fields.

    Returns
    -------
    list
        Four parsed floating-point values.
    """
    result = []
    for start in range(4, 80, 19):
        result.append(_float(line[start:start + 19]))
    return result

def _gps_time(
    epoch: datetime
) -> tuple[int, float]:
    """
    Convert a datetime epoch into GPS week
    and time-of-week.

    Parameters
    ----------
    epoch : datetime

    Returns
    -------
    tuple
        (gps_week, gps_tow)
    """
    if epoch.tzinfo != timezone.utc:
        raise ValueError(
            "epoch must be timezone-aware UTC datetime"
        )

    seconds = (epoch - GPS_EPOCH).total_seconds()
    week = int(seconds // 604800)
    tow = seconds - week * 604800

    return week, tow

def _parse_epoch(first_line: str) -> tuple[str, int, datetime]:
    """
    Parse the first line of a RINEX navigation record.

    Example
    -------
    G01 2025 09 20 00 00 00 ...

    Returns
    -------
    tuple
        (constellation, prn, epoch)
    """

    gnss_id = first_line[0]

    sv_id = int(first_line[1:3])

    year = int(first_line[4:8])
    month = int(first_line[9:11])
    day = int(first_line[12:14])
    hour = int(first_line[15:17])
    minute = int(first_line[18:20])
    second = float(first_line[21:23].strip() or "0")

    sec = int(second)
    microsecond = int(round((second - sec) * 1_000_000))

    if microsecond >= 1_000_000:
        sec += 1
        microsecond -= 1_000_000

    epoch = datetime(
        year, month, day,
        hour, minute, sec,
        microsecond,
        tzinfo=timezone.utc,
    )

    return gnss_id, sv_id, epoch


# ============================================================================
# HEADER PARSING
#
# The RINEX navigation header contains:
#   - RINEX version information
#   - Program metadata
#   - Time system corrections
#   - Ionospheric model parameters
#   - Leap second information
# ============================================================================

def _parse_time_system_correction(
    line: str,
) -> Optional[TimeSystemCorrection]:
    """
    Parse a TIME SYSTEM CORR header record.
    """
    system = line[0:4].strip()
    a0 = _float(line[5:22])
    a1 = _float(line[22:38])
    reference_time = _float(line[38:55])
    reference_week = _int(line[55:60])

    if a0 is None or a1 is None:
        return None

    return TimeSystemCorrection(
        system=system,
        a0=a0,
        a1=a1,
        reference_time=reference_time,
        reference_week=reference_week,
    )


def _parse_ionospheric_correction(
    line: str,
) -> Optional[IonosphericCorrection]:
    """
    Parse an IONOSPHERIC CORR header record.
    """
    system = line[0:4].strip()

    values = []
    for start in range(5, 60, 12):
        value = _float(line[start:start + 12])
        if value is not None:
            values.append(value)

    if not values:
        return None

    return IonosphericCorrection(
        system=system,
        correction_type=system,
        coefficients=tuple(values),
    )


def read_rinex_nav_header(stream) -> RinexNavHeader:
    """
    Read and parse the complete RINEX
    navigation file header.

    Parameters
    ----------
    stream : TextIO

    Returns
    -------
    RinexNavHeader
    """
    version = None
    file_type = ""
    system = None

    program = None
    run_by = None
    date = None

    comments = []
    time_system_corrections = []
    ionospheric_corrections = []
    leap_seconds = None

    for line in stream:
        label = line[60:].strip() if len(line) >= 60 else ""

        if label == "RINEX VERSION / TYPE":
            version = float(line[0:9])
            file_type = line[20:21].strip()

            if len(line) >= 41:
                system = line[40:41].strip() or None

        elif label == "PGM / RUN BY / DATE":
            program = line[0:20].strip() or None
            run_by = line[20:40].strip() or None
            date = line[40:60].strip() or None

        elif label == "COMMENT":
            comments.append(line[:60].rstrip())

        elif label == "TIME SYSTEM CORR":
            corr = _parse_time_system_correction(line)
            if corr is not None:
                time_system_corrections.append(corr)

        elif label == "IONOSPHERIC CORR":
            corr = _parse_ionospheric_correction(line)
            if corr is not None:
                ionospheric_corrections.append(corr)

        elif label == "LEAP SECONDS":
            leap_seconds = _int(line[0:6])

        elif label == "END OF HEADER":
            break

    if version is None:
        raise ValueError("RINEX VERSION / TYPE nem található.")

    return RinexNavHeader(
        version=version,
        file_type=file_type,
        system=system,
        program=program,
        run_by=run_by,
        date=date,
        comments=comments,
        time_system_corrections=time_system_corrections,
        ionospheric_corrections=ionospheric_corrections,
        leap_seconds=leap_seconds,
    )


# ============================================================================
# STANDARD BROADCAST EPHEMERIS RECORDS
#
# GPS, Galileo, BeiDou, QZSS and NavIC use a
# Keplerian orbit representation.
#
# The parser converts the raw fixed-width RINEX
# fields into a unified NavigationData object.
# ============================================================================
def _parse_standard_record(
    first_line: str,
    data_lines: list[str],
) -> BroadcastEphemeris:
    """
    Parse a standard GNSS broadcast ephemeris record.

    Supported systems:
        G - GPS
        E - Galileo
        C - BeiDou
        J - QZSS
        I - NavIC

    Returns
    -------
    NavigationData
    """
    gnss_id, sv_id, epoch = _parse_epoch(first_line)

    record = BroadcastEphemeris(
        gnss_id=gnss_id,
        sv_id=sv_id,
        epoch=epoch,
        time=epoch,
    )

    # Clock is common for GPS/GAL/BDS and most standard NAV records.
    record.af0 = _float(first_line[23:42])
    record.af1 = _float(first_line[42:61])
    record.af2 = _float(first_line[61:80])

    rows = []
    for line in data_lines:
            fields = _fields(line)
            
            if fields != None:
                rows.append(fields)
            else:
                rows.append([None, None, None, None])

    # Missing/short lines are represented by empty fields.
    while len(rows) < 7:
        rows.append([None, None, None, None])

    r2, r3, r4, r5, r6, r7, r8 = rows[:7]

    # Common Keplerian broadcast orbit parameters
    if gnss_id in ("G", "E", "C", "J", "I"):
        record.iode = _as_int(r2[0])
        record.crs = r2[1]
        record.delta_n = r2[2]
        record.m0 = r2[3]

        record.cuc = r3[0]
        record.e = r3[1]
        record.cus = r3[2]
        record.sqrt_a = r3[3]

        record.toe = r4[0]
        record.cic = r4[1]
        record.omega0 = r4[2]
        record.cis = r4[3]

        record.i0 = r5[0]
        record.crc = r5[1]
        record.omega = r5[2]
        record.omega_dot = r5[3]

        record.idot = r6[0]

        if gnss_id in ("G", "J", "I"):
            record.tgd = r7[2]
            record.iodc = _as_int(r7[3])

        # Galileo Broadcast Group Delay parameters
        elif gnss_id == "E":
            # Galileo:
            # r6[1] = data source / codes
            # r6[2] = Galileo week
            # r7[1] = health
            # r7[2] = BGD E1/E5a
            # r7[3] = BGD E1/E5b
            record.bgd_e1_e5a = r7[2]
            record.bgd_e1_e5b = r7[3]
            record.health = _as_int(r7[1])

        # BeiDou dual-frequency group delay parameters
        elif gnss_id == "C":
            # BeiDou:
            # BDS time is handled as record epoch + TOE in the
            # normal RINEX representation. TGD fields are stored.
            record.tgd1 = r7[2]
            record.tgd2 = r7[3]

        if gnss_id in ("G", "E","S","J", "I"):
            record.time = epoch
            # E nanoseconds!

        elif gnss_id == "C":
            record.time = epoch  + timedelta(seconds=14)

    record.gps_week, record.gps_tow = _gps_time(epoch)

    return record


def _as_int(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return int(round(value))


# ============================================================================
# GLONASS BROADCAST RECORDS
#
# Unlike GPS-like systems, GLONASS navigation
# messages provide a state vector rather than
# Keplerian orbital elements.
#
# Parameters include:
#   - Position
#   - Velocity
#   - Acceleration
#   - Clock corrections
# ============================================================================

def _parse_glonass_record(
    first_line: str,
    data_lines: list[str],
) -> BroadcastEphemeris:
    """
    Parse a GLONASS navigation record.

    Returns
    -------
    BroadcastEphemeris
    """
    gnss_id, sv_id, epoch = _parse_epoch(first_line)

    record = BroadcastEphemeris(
        gnss_id=gnss_id,
        sv_id=sv_id,
        epoch=epoch,
        time=epoch,
    )

    record.af0 = _float(first_line[23:42])
    record.af1 = _float(first_line[42:61])
    record.af2 = _float(first_line[61:80])

    rows = []
    for line in data_lines:
        if len(line) >= 80:
            fields = _fields(line)
            rows.append(fields)
        else:
            rows.append([None, None, None, None])

    while len(rows) < 3:
        rows.append([None, None, None, None])

    r2, r3, r4 = rows[:3]

    # GLONASS RINEX NAV:
    #
    # line 2: X, Xdot, Xdotdot, health
    # line 3: Y, Ydot, Ydotdot, Bn
    # line 4: Z, Zdot, Zdotdot, frequency channel
    #
    # Az X/Y/Z acceleration values are represented by Xdotdot etc.

    record.x = r2[0]
    record.vx = r2[1]
    record.ax = r2[2]
    record.health = _as_int(r2[3])

    record.y = r3[0]
    record.vy = r3[1]
    record.ay = r3[2]
    record.freq_channel = _as_int(r3[3]) 

    record.z = r4[0]
    record.vz = r4[1]
    record.az = r4[2]
    record.age_of_operation = _as_int(r4[3])

    # GLONASS clock parameters
    record.tau_n = record.af0
    record.gamma = record.af1

    # GLONASS epoch is UTC(SU)-like rather than GPS time.
    # We deliberately do not derive GPS week/TOW from it here.
    record.gps_week = None
    record.gps_tow = None

    # leap seconds kezelését kivettem
    leap_seconds = get_leap_seconds (epoch)

    record.time = epoch + timedelta(seconds=leap_seconds)
    #record.time = epoch
    

    return record


# ============================================================================
# RECORD READER
# ============================================================================

def _read_one_record(
    first_line: str,
    stream,
    version: float,
) -> BroadcastEphemeris:
    """
    Read one complete navigation record from
    the file stream.

    The function automatically determines the
    record format based on the constellation
    identifier.

    Returns
    -------
    BroadcastEphemeris
    """

    gnss_id = first_line[0]

    # Standard RINEX NAV records are 8 lines for GPS/GAL/BDS/QZSS/NavIC.
    # GLONASS records are 4 lines.
    number_of_following_lines = 3 if gnss_id  in ("R", "S")  else 7

    data_lines = []

    for _ in range(number_of_following_lines):
        line = stream.readline()

        if not line:
            raise ValueError("Hiányos RINEX NAV rekord.")

        data_lines.append(line.rstrip("\n"))

    if gnss_id == "R":
        return _parse_glonass_record(
            first_line,
            data_lines,
        )

    return _parse_standard_record(
        first_line,
        data_lines,
    )


def read_rinex3_navigation_records(
    stream,
    header: RinexNavHeader,
) -> list[BroadcastEphemeris]:
    """
    Read all RINEX 3 navigation records.
    """
    records = []

    while True:
        line = stream.readline()

        if not line:
            break

        if not line.strip():
            continue

        # RINEX NAV record mindig GNSS karakterrel indul:
        # G/E/C/R/J/I/S...
        if line[0] not in "GRECJIS":
            continue

        try:
            record = _read_one_record(
                line.rstrip("\n"),
                stream,
                header.version,
            )
            records.append(record)

        except (ValueError, IndexError) as exc:
            raise ValueError(
                f"Hibás NAV rekord: {line.rstrip()!r}"
            ) from exc

    return records


# ============================================================================
# RINEX 4
#
# A RINEX 4 NAV rekordok alapvető adatblokkjai kompatibilisek a fenti
# rendszer-specifikus mappinggel, de a message type miatt a tényleges
# rekordfelismerés szigorúbb lehet.
#
# Az itt használt parser a standard műholdas NAV blokkokat kezeli.
# ============================================================================

def read_rinex4_navigation_records(
    stream,
    header: RinexNavHeader,
) -> list[BroadcastEphemeris]:
    """
    Read all RINEX 4 navigation records.
    """
    records = []

    while True:
        line = stream.readline()

        if not line:
            break

        if not line.strip():
            continue

        # RINEX 4 első karaktere GNSS azonosító.
        if line[0] not in "GRECJIS":
            continue

        record = _read_one_record(
            line.rstrip("\n"),
            stream,
            header.version,
        )

        records.append(record)

    return records


# ============================================================================
# PUBLIC API
# ============================================================================

def read_rinex_navigation(
    filename: str | Path,
) -> RinexNavigationFile:
    """
    Read a RINEX navigation file.

    The parser automatically detects the
    RINEX version and dispatches to the
    appropriate record reader.

    Parameters
    ----------
    filename : str | Path

    Returns
    -------
    RinexNavigationFile
        Parsed header and navigation records.
    """
    filename = Path(filename)

    with filename.open(
        "r",
        encoding="ascii",
        errors="replace",
    ) as stream:

        header = read_rinex_nav_header(stream)

        if header.version < 4.0:
            records = read_rinex3_navigation_records(
                stream,
                header,
            )
        else:
            records = read_rinex4_navigation_records(
                stream,
                header,
            )

    return RinexNavigationFile(
        header=header,
        records=records,
    )


# ============================================================================
# OPTIONAL CONVENIENCE
# ============================================================================

def read_rinex_navigation_file(
    filename: str | Path,
) -> RinexNavigationFile:
    """Alias a rövidebb API névhez."""
    return read_rinex_navigation(filename)

def get_leap_seconds(epoch: datetime) -> int:
    """
    Return the GPS-UTC leap second offset
    valid for the specified epoch.

    The values are based on the historical
    leap second table published by the IERS.

    Parameters
    ----------
    epoch : datetime

    Returns
    -------
    int
        GPS minus UTC offset in seconds.
    """
    if epoch.tzinfo != timezone.utc:
        raise ValueError(
            "epoch must be timezone-aware UTC datetime"
        )

    LEAP_HISTORY = [
        (datetime(2017, 1, 1, 0, 0, tzinfo=timezone.utc), 18),
        (datetime(2015, 7, 1, 0, 0, tzinfo=timezone.utc), 17),
        (datetime(2012, 7, 1, 0, 0, tzinfo=timezone.utc), 16),
        (datetime(2009, 1, 1, 0, 0, tzinfo=timezone.utc), 15),
        (datetime(2006, 1, 1, 0, 0, tzinfo=timezone.utc), 14),
        (datetime(1999, 1, 1, 0, 0, tzinfo=timezone.utc), 13),
        (datetime(1997, 7, 1, 0, 0, tzinfo=timezone.utc), 12),
        (datetime(1996, 1, 1, 0, 0, tzinfo=timezone.utc), 11),
        (datetime(1994, 7, 1, 0, 0, tzinfo=timezone.utc), 10),
        (datetime(1993, 7, 1, 0, 0, tzinfo=timezone.utc), 9),
        (datetime(1992, 7, 1, 0, 0, tzinfo=timezone.utc), 8),
        (datetime(1991, 1, 1, 0, 0, tzinfo=timezone.utc), 7),
        (datetime(1990, 1, 1, 0, 0, tzinfo=timezone.utc), 6),
        (datetime(1988, 1, 1, 0, 0, tzinfo=timezone.utc), 5),
        (datetime(1985, 7, 1, 0, 0, tzinfo=timezone.utc), 4),
        (datetime(1983, 7, 1, 0, 0, tzinfo=timezone.utc), 3),
        (datetime(1982, 7, 1, 0, 0, tzinfo=timezone.utc), 2),
        (datetime(1981, 7, 1, 0, 0, tzinfo=timezone.utc), 1),
        (datetime(1980, 1, 6, 0, 0, tzinfo=timezone.utc), 0) # GPS kezdőpont
    ]

    # Megkeressük az epoch-hoz passzoló legfrissebb érvényes értéket
    for switch_date, leap_val in LEAP_HISTORY:
        if epoch >= switch_date:
            return leap_val
            
    return 0  # 1980 előtti időpontok esetén (bár RINEX-nél ilyen nem lesz)
