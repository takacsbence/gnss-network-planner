"""
UBX MGA almanac decoder.

Supports decoding of GPS, Galileo, BeiDou, QZSS and GLONASS
almanac messages from u-blox MGA-ANO/MGA-ALM data streams.

The decoded records are returned as AlmanacRecord instances.
"""

import struct
import math
import logging

logger = logging.getLogger(__name__)

from pathlib import Path
from typing import Iterator

from src.almanac.models import AlmanacRecord
from src.utils.constants import *

UBX_SYNC1 = 0xB5
UBX_SYNC2 = 0x62

MGA_CLASS = 0x13


# --- Almanac decoders (u-blox F9/M8 Interface Description) -------------------


def decode_gps_like(p: bytes, system: str) -> AlmanacRecord:
    """
    Decode MGA-GPS-ALM and MGA-QZSS-ALM records.
    """

    (
        _t,
        _v,
        sv,
        health,
        e,
        wna,
        toa,
        di,
        odot,
        sqrta,
        om0,
        w,
        m0,
        af0,
        af1,
    ) = struct.unpack_from("<BBBBHBBhhIiiihh", p)

    if system == "GPS":
        i0_half_cycles = 0.30
        gnss_id = "G"
    else:
        # QZO: 0.25 semi-circles
        # GEO (QZS-3): 0.0 semi-circles
        i0_half_cycles = 0.0 if sv == 7 else 0.25
        gnss_id = "J"

    return AlmanacRecord(
        gnss_id=gnss_id,
        sv_id=sv,

        week=wna,
        toa=toa * 4096.0,

        e=e * 2**-21,
        i0=(i0_half_cycles + di * 2**-19) * SC,

        omega_dot=odot * 2**-38 * SC,
        sqrt_a=sqrta * 2**-11,

        omega0=om0 * 2**-23 * SC,
        omega=w * 2**-23 * SC,
        m0=m0 * 2**-23 * SC,

        af0=af0 * 2**-20,
        af1=af1 * 2**-38,

        health=health,
    )

def decode_gal(payload: bytes) -> AlmanacRecord:
    """
    Decode an MGA-GAL-ALM record.
    """

    (_t, _v, sv, _r, ioda, wna, toa, dsqa, e, di, om0, odot, w, m0, af0, af1, h5b, h1b) = \
        struct.unpack_from("<BBBBBBHhHhhhhhhhBB", payload)

    return AlmanacRecord(
        gnss_id="E",
        sv_id=sv,
        week=wna,
        toa=toa * 600.0,

        e=e * 2 ** -16,
        i0=(56 / 180 + di * 2 ** -14) * SC,

        omega0=om0 * 2 ** -15 * SC,
        omega=w * 2 ** -15 * SC,
        m0=m0 * 2 ** -15 * SC,

        omega_dot=odot * 2 ** -33 * SC,
        sqrt_a=math.sqrt(29600000.0) + dsqa * 2 ** -9,

        af0=af0 * 2 ** -19,
        af1=af1 * 2 ** -38,

        health=(h1b << 4) | h5b,
    )

def decode_bds(payload: bytes) -> AlmanacRecord:
    """
    Decode MGA-BDS-ALM record.
    """

    (
        _t,
        _v,
        sv,
        _r,
        wna,
        toa,
        di,
        sqrta,
        e,
        w,
        m0,
        om0,
        odot,
        a0,
        a1,
    ) = struct.unpack_from("<BBBBBBhIIiiiihh", payload)

    geo = sv <= 5 or sv >= 59
    i0_half_cycles = 0.0 if geo else 0.30

    return AlmanacRecord(
        gnss_id="C",
        sv_id=sv,

        week=wna,
        toa=toa * 4096.0,

        e=e * 2**-21,
        i0=(i0_half_cycles + di * 2**-19) * SC,

        sqrt_a=sqrta * 2**-11,

        omega0=om0 * 2**-23 * SC,
        omega=w * 2**-23 * SC,
        m0=m0 * 2**-23 * SC,

        omega_dot=odot * 2**-38 * SC,

        af0=a0 * 2**-20,
        af1=a1 * 2**-38,

        health=0,
        is_geo=geo,
    )

def decode_glo(payload: bytes) -> AlmanacRecord:
    """
    Decode an MGA-GLO-ALM record.
    """
    (
        _t,
        _v,
        sv,
        _r,
        n,
        m,
        c,
        tau,
        eps,
        lam,
        di,
        tlam,
        dT,
        dTdot,
        h,
        w,
    ) = struct.unpack_from(
        "<BBBBHBBhHiiIibbh",
        payload,
    )

    return AlmanacRecord(
        gnss_id="R",
        sv_id=sv,

        health=c,

        glonass_n=n,
        glonass_m=m,
        glonass_h=h,

        tau=tau * 2**-18,

        e=eps * 2**-20,

        lam=lam * 2**-20 * SC,
        di=di * 2**-20 * SC,

        tlam=tlam * 2**-5,

        dT=dT * 2**-9,
        dTdot=dTdot * 2**-14,

        omega=w * 2**-15 * SC,
    )




def iter_ubx_frames(blob: bytes) -> Iterator[AlmanacRecord]:
    """
    Iterate over all almanac records contained in a UBX file.

    Parameters
    ----------
    filename
        Path to the UBX file.

    Yields
    ------
    AlmanacRecord
        Decoded almanac records.
    """

    i = 0
    n = len(blob)

    while i + 8 <= n:

        if blob[i] != UBX_SYNC1 or blob[i + 1] != UBX_SYNC2:
            i += 1
            continue

        msg_class = blob[i + 2]
        msg_id = blob[i + 3]

        payload_len = blob[i + 4] | (blob[i + 5] << 8)

        frame_end = i + 8 + payload_len

        if frame_end > n:
            break

        payload = blob[i + 6 : i + 6 + payload_len]

        yield msg_class, msg_id, payload

        i = frame_end


def decode_mga_message(
    msg_id: int,
    payload: bytes,
) -> AlmanacRecord | None:
    """
    Decode a single MGA almanac message.

    Parameters
    ----------
    msg_id
        UBX MGA message identifier.
    payload
        Raw UBX message payload.

    Returns
    -------
    AlmanacRecord | None
        Decoded almanac record, or None if the message is
        unsupported or decoding fails.
    """
    DECODERS = {
        0x00: lambda p: decode_gps_like(p, "GPS"),
        0x02: decode_gal,
        0x03: decode_bds,
        0x05: lambda p: decode_gps_like(p, "QZS"),
        0x06: decode_glo,
    }

    try:
        decoder = DECODERS.get(msg_id)

        if decoder is None:
            return None

        return decoder(payload)


    except Exception:
        logger.exception(
            "Failed to decode MGA message 0x%02X",
            msg_id,
        )
        return None



def iter_almanac_records(
    filename: str | Path,
) -> Iterator:
    """
    Iterate over all almanac records in a UBX file.
    """

    filename = Path(filename)

    with filename.open("rb") as f:
        blob = f.read()

    for msg_class, msg_id, payload in iter_ubx_frames(blob):

        if msg_class != MGA_CLASS:
            continue

        record = decode_mga_message(
            msg_id,
            payload,
        )

        if record is not None:
            yield record
