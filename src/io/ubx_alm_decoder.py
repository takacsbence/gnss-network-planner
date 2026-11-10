import struct
import math

from pathlib import Path
from typing import Iterator


UBX_SYNC1 = 0xB5
UBX_SYNC2 = 0x62

MGA_CLASS = 0x13

PI = math.pi
SC = PI  # félkör -> radián

# --- Dekóderek (u-blox F9 / M8 interface description szerint) ----------------
def dec_gps_like(p, system):
    """MGA-GPS-ALM és MGA-QZSS-ALM (36 bájt, azonos kiosztás)."""
    (_t, _v, sv, health, e, wna, toa, di, odot, sqrta, om0, w, m0, af0, af1) = \
        struct.unpack_from("<BBBBHBBhhIiiihh", p)
    if system == "GPS":
        i0, prn = 0.30, f"G{sv:02d}"
    else:
        # QZSS: QZO pályánál i0 = 0,25 félkör; GEO (QZS-3, PRN 199) esetén 0
        i0, prn = (0.0 if sv == 7 else 0.25), f"J{sv:02d}"
    return dict(sys=system, prn=prn, sv=sv, health=health, wna=wna, toa=toa * 4096,
                e=e * 2**-21, i=(i0 + di * 2**-19) * SC, omegadot=odot * 2**-38 * SC,
                sqrta=sqrta * 2**-11, omega0=om0 * 2**-23 * SC, w=w * 2**-23 * SC,
                m0=m0 * 2**-23 * SC, af0=af0 * 2**-20, af1=af1 * 2**-38)


def dec_gal(p):
    (_t, _v, sv, _r, ioda, wna, toa, dsqa, e, di, om0, odot, w, m0, af0, af1, h5b, h1b) = \
        struct.unpack_from("<BBBBBBHhHhhhhhhhBB", p)
    return dict(sys="GAL", prn=f"E{sv:02d}", sv=sv, health=(h1b << 4) | h5b, wna=wna,
                toa=toa * 600, e=e * 2**-16, i=(56 / 180 + di * 2**-14) * SC,
                omegadot=odot * 2**-33 * SC, sqrta=math.sqrt(29600000.0) + dsqa * 2**-9,
                omega0=om0 * 2**-15 * SC, w=w * 2**-15 * SC, m0=m0 * 2**-15 * SC,
                af0=af0 * 2**-19, af1=af1 * 2**-38, ioda=ioda)


def dec_bds(p):
    (_t, _v, sv, _r, wna, toa, di, sqrta, e, w, m0, om0, odot, a0, a1) = \
        struct.unpack_from("<BBBBBBhIIiiiihh", p)
    geo = sv <= 5 or sv >= 59
    i0 = 0.0 if geo else 0.30
    return dict(sys="BDS", prn=f"C{sv:02d}", sv=sv, health=0, wna=wna, toa=toa * 4096,
                e=e * 2**-21, i=(i0 + di * 2**-19) * SC, omegadot=odot * 2**-38 * SC,
                sqrta=sqrta * 2**-11, omega0=om0 * 2**-23 * SC, w=w * 2**-23 * SC,
                m0=m0 * 2**-23 * SC, af0=a0 * 2**-20, af1=a1 * 2**-38, geo=geo)


def dec_glo(p):
    (_t, _v, sv, _r, n, m, c, tau, eps, lam, di, tlam, dT, dTdot, h, w) = \
        struct.unpack_from("<BBBBHBBhHiiIibbh", p)
    return dict(sys="GLO", prn=f"R{sv:02d}", sv=sv, health=c, N=n, M=m, H=h,
                tau=tau * 2**-18, e=eps * 2**-20, lam=lam * 2**-20 * SC,
                di=di * 2**-20 * SC, tlam=tlam * 2**-5, dT=dT * 2**-9,
                dTdot=dTdot * 2**-14, w=w * 2**-15 * SC)




def iter_ubx_frames(blob: bytes) -> Iterator[tuple[int, int, bytes]]:
    """
    Iterate through UBX frames.

    Yields:
        (msg_class, msg_id, payload)
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
) -> dict | None:
    """
    Decode a single MGA almanac message.

    Returns
    -------
    dict | None
    """


    try:

        #
        # GPS
        #
        if msg_id == 0x00:
            return dec_gps_like(payload, "GPS")

        #
        # QZSS
        #
        if msg_id == 0x05:
            return dec_gps_like(payload, "QZS")

        #
        # Galileo
        #
        if msg_id == 0x02:
            return dec_gal(payload)

        #
        # BeiDou
        #
        if msg_id == 0x03:
            return dec_bds(payload)

        #
        # GLONASS
        #
        if msg_id == 0x06:
            return dec_glo(payload)

    except Exception as e:
        return None

    return None


def iter_almanac_records(
    filename: str | Path,
):
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
