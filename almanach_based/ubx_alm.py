#!/usr/bin/env python3
"""
UBX AssistNow almanach dekóder és pályaszámító.

Beolvassa az UBX-MGA-*-ALM üzeneteket (GPS, Galileo, BeiDou, QZSS, GLONASS),
kiírja a dekódolt almanach-paramétereket, és kiszámolja a műholdak ECEF
pozícióját és órahibáját egy adott időpontra. Megadott vevőpozícióval
azimutot és elevációt is számol.

Használat:
    python3 ubx_alm.py alm.ubx
    python3 ubx_alm.py alm.ubx --time "2026-10-21 12:00:00" --pos 47.5,19.05,150
    python3 ubx_alm.py alm.ubx --csv-prefix ki/   (alm_params.csv, alm_positions.csv)

Az időpont UTC. Ha nincs megadva, a fájlban lévő MGA-INI-TIME-UTC idejét
használja (ez a letöltés ideje), ha az sincs, akkor a mostani időt.
Csak a Python standard könyvtárát használja.
"""
import argparse
import csv
import math
import os
import struct
import sys
from datetime import datetime, timedelta, timezone

PI = math.pi
SC = PI  # félkör -> radián

# --- Időrendszerek -----------------------------------------------------------
GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
LEAP_GPS_UTC = 18  # GPS-UTC 2017 óta; felülírja az MGA-INI-TIME-UTC, ha van benne
BDT_GPST = 14      # GPST - BDT, másodperc
BDS_WEEK_OFFSET = 1356
GST_WEEK_OFFSET = 1024


def gps_week_tow(t_utc, leap):
    s = (t_utc - GPS_EPOCH).total_seconds() + leap
    w = int(s // 604800)
    return w, s - w * 604800


def full_week(cur_week, wna, modulus):
    """A csonkolt almanach-hétszámból a mostanihoz legközelebbi teljes hét."""
    wa = cur_week - ((cur_week - wna) % modulus)
    if cur_week - wa > modulus // 2:
        wa += modulus
    return wa


# --- UBX keretek -------------------------------------------------------------
def ubx_frames(blob):
    i = 0
    while i + 8 <= len(blob):
        if blob[i:i + 2] != b"\xb5\x62":
            i += 1
            continue
        n = int.from_bytes(blob[i + 4:i + 6], "little")
        msg = blob[i:i + n + 8]
        if len(msg) < n + 8:
            break
        a = b = 0
        for x in msg[2:-2]:
            a = (a + x) & 0xFF
            b = (b + a) & 0xFF
        if bytes([a, b]) == msg[-2:]:
            yield msg[2], msg[3], msg[6:-2]
            i += n + 8
        else:
            i += 1


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


# --- Pályaszámítás -----------------------------------------------------------
CONST = {  # mu [m^3/s^2], Föld forgási szögsebesség [rad/s]
    "GPS": (3.986005e14, 7.2921151467e-5),
    "QZS": (3.986005e14, 7.2921151467e-5),
    "GAL": (3.986004418e14, 7.2921151467e-5),
    "BDS": (3.986004418e14, 7.2921150e-5),
}


def kepler(M, e):
    E = M
    for _ in range(30):
        dE = (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
        E -= dE
        if abs(dE) < 1e-13:
            break
    return E


def pos_kepler(a, tk):
    """IS-GPS-200 almanach algoritmus (Galileo/BeiDou/QZSS ugyanígy)."""
    mu, we = CONST[a["sys"]]
    A = a["sqrta"] ** 2
    n = math.sqrt(mu / A**3)
    E = kepler(a["m0"] + n * tk, a["e"])
    nu = math.atan2(math.sqrt(1 - a["e"]**2) * math.sin(E), math.cos(E) - a["e"])
    u = nu + a["w"]
    r = A * (1 - a["e"] * math.cos(E))
    Om = a["omega0"] + (a["omegadot"] - we) * tk - we * a["toa"]
    xp, yp = r * math.cos(u), r * math.sin(u)
    ci, si = math.cos(a["i"]), math.sin(a["i"])
    x = xp * math.cos(Om) - yp * ci * math.sin(Om)
    y = xp * math.sin(Om) + yp * ci * math.cos(Om)
    z = yp * si
    clk = a["af0"] + a["af1"] * tk
    return x, y, z, clk


# GLONASS (ICD L1/L2 2008, A.3.1.3 egyszerűsített algoritmus, rövid periódusú
# perturbációk nélkül; ez néhány km-es hibát ad, almanachhoz bőven elég)
GLO_MU = 398600.4418e9
GLO_AE = 6378136.0
GLO_J20 = 1082625.75e-9
GLO_WE = 7.2921151467e-5


def glo_epoch(N, t_utc):
    """A GLONASS almanach N napjának kezdete (00:00 MSK) UTC-ben, a négyéves
    ciklust a megadott időponthoz legközelebbire választva."""
    best = None
    for leap_year in range(t_utc.year - 8, t_utc.year + 5):
        if leap_year % 4:
            continue
        d = datetime(leap_year, 1, 1, tzinfo=timezone.utc) + timedelta(days=N - 1) - timedelta(hours=3)
        if best is None or abs((d - t_utc).total_seconds()) < abs((best - t_utc).total_seconds()):
            best = d
    return best


def pos_glo(a, t_utc):
    t0 = glo_epoch(a["N"], t_utc) + timedelta(seconds=a["tlam"])
    dt = (t_utc - t0).total_seconds()
    i = (63 / 180) * PI + a["di"]
    Tav = 43200 + a["dT"]
    W = math.floor(dt / Tav)
    Tdr = Tav + (2 * W + 1) * a["dTdot"]
    n = 2 * PI / Tdr
    e, w0 = a["e"], a["w"]
    # félnagytengely iterációval
    aa = (Tdr / (2 * PI)) ** (2 / 3) * GLO_MU ** (1 / 3)
    for _ in range(20):
        p = aa * (1 - e**2)
        k = 1.5 * GLO_J20 * (GLO_AE / p) ** 2
        Tosk = Tdr / (1 - k * ((2 - 2.5 * math.sin(i)**2) * (1 - e**2) ** 1.5 /
                               (1 + e * math.cos(w0))**2 +
                               (1 + e * math.cos(w0))**3 / (1 - e**2)))
        new = (Tosk / (2 * PI)) ** (2 / 3) * GLO_MU ** (1 / 3)
        if abs(new - aa) < 1e-3:
            aa = new
            break
        aa = new
    p = aa * (1 - e**2)
    Omdot = -1.5 * GLO_J20 * n * (GLO_AE / p)**2 * math.cos(i)
    wdot = -0.75 * GLO_J20 * n * (GLO_AE / p)**2 * (1 - 5 * math.cos(i)**2)
    lam = a["lam"] + (Omdot - GLO_WE) * dt
    w = w0 + wdot * dt
    # átlagos szélességi argumentum a csomóponttól
    E0 = -2 * math.atan(math.sqrt((1 - e) / (1 + e)) * math.tan(w0 / 2))
    L1 = w0 + E0 - e * math.sin(E0)
    L2 = L1 + n * (dt - (W * Tav + a["dTdot"] * W**2))
    M = L2 - w
    E = kepler(M, e)
    nu = math.atan2(math.sqrt(1 - e**2) * math.sin(E), math.cos(E) - e)
    u = nu + w
    r = aa * (1 - e * math.cos(E))
    x = r * (math.cos(lam) * math.cos(u) - math.sin(lam) * math.sin(u) * math.cos(i))
    y = r * (math.sin(lam) * math.cos(u) + math.cos(lam) * math.sin(u) * math.cos(i))
    z = r * math.sin(u) * math.sin(i)
    return x, y, z, a["tau"], dt


# --- Segédfüggvények ---------------------------------------------------------
def geodetic_to_ecef(lat, lon, h):
    a, f = 6378137.0, 1 / 298.257223563
    e2 = f * (2 - f)
    la, lo = math.radians(lat), math.radians(lon)
    N = a / math.sqrt(1 - e2 * math.sin(la)**2)
    return ((N + h) * math.cos(la) * math.cos(lo),
            (N + h) * math.cos(la) * math.sin(lo),
            (N * (1 - e2) + h) * math.sin(la))


def az_el(rx, sat, lat, lon):
    dx = [s - r for s, r in zip(sat, rx)]
    la, lo = math.radians(lat), math.radians(lon)
    e = -math.sin(lo) * dx[0] + math.cos(lo) * dx[1]
    n = (-math.sin(la) * math.cos(lo) * dx[0] - math.sin(la) * math.sin(lo) * dx[1]
         + math.cos(la) * dx[2])
    u = (math.cos(la) * math.cos(lo) * dx[0] + math.cos(la) * math.sin(lo) * dx[1]
         + math.sin(la) * dx[2])
    return (math.degrees(math.atan2(e, n)) % 360,
            math.degrees(math.atan2(u, math.hypot(e, n))))


def parse_time(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise SystemExit(f"Ismeretlen időformátum: {s}")


# --- Fő program --------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--time", help="Számítási időpont UTC-ben, pl. '2026-10-21 12:00:00'")
    ap.add_argument("--pos", help="Vevőpozíció: szélesség,hosszúság,magasság (fok,fok,m)")
    ap.add_argument("--csv-prefix", default="", help="CSV kimenetek helye/előtagja")
    ap.add_argument("--all", action="store_true", help="A horizont alatti műholdakat is listázza")
    args = ap.parse_args()

    blob = open(args.file, "rb").read()
    alms, ini_time, leap = [], None, LEAP_GPS_UTC
    for cls, mid, p in ubx_frames(blob):
        if cls != 0x13:
            continue
        if mid == 0x40 and p[0] == 0x10 and len(p) >= 24:  # MGA-INI-TIME-UTC
            (_t, _v, _ref, ls, yr, mo, dy, hh, mm, ss, _r, ns) = struct.unpack_from("<BBBbHBBBBBBI", p)
            ini_time = datetime(yr, mo, dy, hh, mm, ss, tzinfo=timezone.utc) + timedelta(microseconds=ns / 1000)
            if ls not in (-128, 0):
                leap = ls
        elif p and p[0] == 0x02:  # ALM típus
            dec = {0x00: lambda q: dec_gps_like(q, "GPS"), 0x05: lambda q: dec_gps_like(q, "QZS"),
                   0x02: dec_gal, 0x03: dec_bds, 0x06: dec_glo}.get(mid)
            if dec:
                alms.append(dec(p))

    if not alms:
        raise SystemExit("Nincs MGA-*-ALM üzenet a fájlban.")

    t = parse_time(args.time) if args.time else (ini_time or datetime.now(timezone.utc))
    gw, gtow = gps_week_tow(t, leap)
    print(f"Fájl: {args.file}   almanach üzenetek: {len(alms)}")
    if ini_time:
        print(f"Letöltés ideje (MGA-INI-TIME-UTC): {ini_time:%Y-%m-%d %H:%M:%S} UTC")
    print(f"Számítási idő: {t:%Y-%m-%d %H:%M:%S} UTC  (GPS hét {gw}, TOW {gtow:.0f} s)\n")

    rx = None
    if args.pos:
        lat, lon, h = (float(v) for v in args.pos.split(","))
        rx = geodetic_to_ecef(lat, lon, h)

    rows = []
    for a in alms:
        s = a["sys"]
        if s == "GLO":
            x, y, z, clk, tk = pos_glo(a, t)
            age = tk
            week = ""
        else:
            if s in ("GPS", "QZS"):
                cw, tow, mod = gw, gtow, 256
            elif s == "GAL":
                cw, tow, mod = gw - GST_WEEK_OFFSET, gtow, 4
            else:  # BDS
                bs = gw * 604800 + gtow - BDT_GPST
                cw, tow, mod = int(bs // 604800) - BDS_WEEK_OFFSET, bs % 604800, 256
            wa = full_week(cw, a["wna"], mod)
            tk = (cw - wa) * 604800 + (tow - a["toa"])
            x, y, z, clk = pos_kepler(a, tk)
            age, week = tk, wa
        r = math.sqrt(x * x + y * y + z * z)
        if s == "GLO":
            ok = a["health"] == 1          # GLONASS: C=1 jelenti az üzemképest
        elif s == "BDS":
            ok = None                      # az MGA-BDS-ALM nem tartalmaz health mezőt
        else:
            ok = a["health"] == 0
        status = "ok" if ok else ("–" if ok is None else "hibás")
        if abs(age) > 7 * 86400:
            status += ",ELAVULT"
        row = dict(prn=a["prn"], sys=s, health=a["health"], status=status, week=week,
                   age_h=round(age / 3600, 2), x_m=round(x, 1), y_m=round(y, 1), z_m=round(z, 1),
                   r_km=round(r / 1000, 1), clk_us=round(clk * 1e6, 3))
        if rx:
            az, el = az_el(rx, (x, y, z), lat, lon)
            row.update(az_deg=round(az, 1), el_deg=round(el, 1))
        rows.append(row)

    # paraméter CSV
    pfx = args.csv_prefix
    if pfx and pfx.endswith("/"):
        os.makedirs(pfx, exist_ok=True)
    keys = sorted({k for a in alms for k in a})
    with open(f"{pfx}alm_params.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["prn", "sys"] + [k for k in keys if k not in ("prn", "sys")])
        wr.writeheader()
        for a in alms:
            wr.writerow({k: (f"{v:.12g}" if isinstance(v, float) else v) for k, v in a.items()})
    with open(f"{pfx}alm_positions.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    # konzol összefoglaló
    print("Rendszer  db   pályasugár [km]   inklináció [fok]")
    for s in ("GPS", "GAL", "BDS", "QZS", "GLO"):
        sel = [(r, a) for r, a in zip(rows, alms) if r["sys"] == s]
        if not sel:
            continue
        rr = [r["r_km"] for r, _ in sel]
        inc = [math.degrees(a["i"] if s != "GLO" else 63 / 180 * PI + a["di"]) for _, a in sel]
        print(f"  {s:4}   {len(sel):3}   {min(rr):8.0f}–{max(rr):<8.0f}  {min(inc):6.2f}–{max(inc):.2f}")
    print()

    show = rows if (args.all or not rx) else [r for r in rows if r["el_deg"] > 0]
    if rx:
        show = sorted(show, key=lambda r: -r["el_deg"])
        print(f"Látható műholdak ({len(show)} db) a megadott pozícióból:")
        print(f"{'PRN':5} {'állapot':12} {'az':>6} {'el':>6} {'r [km]':>8} {'óra [µs]':>10}")
        for r in show:
            print(f"{r['prn']:5} {r['status']:12} {r['az_deg']:6.1f} {r['el_deg']:6.1f} {r['r_km']:8.0f} {r['clk_us']:10.2f}")
    else:
        print(f"{'PRN':5} {'állapot':12} {'X [km]':>10} {'Y [km]':>10} {'Z [km]':>10} {'óra [µs]':>10} {'kor [h]':>8}")
        for r in show:
            print(f"{r['prn']:5} {r['status']:12} {r['x_m']/1e3:10.1f} {r['y_m']/1e3:10.1f} "
                  f"{r['z_m']/1e3:10.1f} {r['clk_us']:10.2f} {r['age_h']:8.1f}")
    bad = [r["prn"] for r in rows if "ELAVULT" in r["status"]]
    if bad:
        print(f"\nFigyelem, 7 napnál régebbi almanach (pozíciójuk pontatlan lehet): {', '.join(bad)}")
    print(f"\nCSV: {pfx}alm_params.csv, {pfx}alm_positions.csv")


if __name__ == "__main__":
    main()
