#!/usr/bin/env python3
"""
Állomásrács + többnapos almanach-pályaszámítás + közös műholdak szomszédos
állomások között, konstellációnként.

Az ubx_alm.py-t használja (ugyanabban a mappában legyen). Csak standard könyvtár.

Rács:
  --sides 6  : háromszögrács (hatszögletű elrendezés) a kezdőpont körül.
               --rings N gyűrű: N=1 -> 7 állomás, N=2 -> 19, N=3 -> 37.
               Minden szomszédos állomáspár távolsága = --edge.
  --sides 5  : a kezdőpont + köré egy szabályos ötszög, oldalhossz = --edge.
               (Ötszöggel síkot nem lehet hézagmentesen kitölteni, ezért itt
               csak egy gyűrű van, és a középpont-csúcs távolság 0,851*edge.)
  --max-dist : terület lefedése (csak --sides 6): a kezdőponttól ennyi km-en
               belüli összes rácspont állomás lesz, a gyűrűszámot magától adja.
  --area     : GeoJSON poligon (pl. országhatár) lefedése (csak --sides 6). A
               kezdőpontból indul a rács; ha nincs --lat/--lon, a terület
               középpontjából. --border-buffer km: a határ menti sáv is.
  --stations : kézi állomáslista (txt/csv) a rács helyett, soronként:
                 [név] szélesség hosszúság [magasság_m]
               Szomszédság: --neighbors delaunay | knn:K | dist:KM, vagy
               --pairs fájl (soronként két név); --max-edge KM a hosszú
               párok elhagyására. --area mellett a határ csak háttér lesz.
  --html     : interaktív, időben lejátszható térkép + grafikon (HTML).
  --no-center: a kezdőpont nem állomás, csak a sokszög csúcsai (csak rings=1).
  --rot      : a rács elforgatása fokban (0 = az egyik csúcs pontosan északra esik).

Példák:
  python3 grid_vis.py alm.ubx --lat 47.0 --lon 19.0 --h 150 --edge 20 --sides 6 --rings 1
  python3 grid_vis.py alm.ubx --lat 47.0 --lon 19.0 --edge 50 --max-dist 300 --no-azel
  python3 grid_vis.py alm.ubx --area hu.json --edge 20 --days 5 --step 15 --no-azel --html
  python3 grid_vis.py alm.ubx --stations allomasok.txt --area hu.json --html --no-azel
  python3 grid_vis.py alm.ubx --stations allomasok.txt --neighbors knn:4 --max-edge 80
  python3 grid_vis.py alm.ubx --lat 47.0 --lon 19.0 --edge 50 --sides 5 --days 5 --step 15 --mask 10

Kimenetek (--out mappa, alapért.: grid_out/):
  stations.csv     állomások (név, szélesség, hosszúság, magasság)
  edges.csv        szomszédos párok és a valódi geodéziai távolságuk
  azel.csv         epoch, állomás, PRN, azimut, eleváció (csak a maszk fölött)
  common.csv       epoch, pár, rendszer, közös db, látható db A-n, látható db B-n
  summary.csv      páronként és rendszerenként min / átlag / max közös műhold
"""
import argparse
import collections
import csv
import json
import math
import os
import struct
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ubx_alm as U  # noqa: E402

SYS_ORDER = ["GPS", "GAL", "GLO", "BDS", "QZS"]

# --- WGS84 geodézia (Vincenty) ----------------------------------------------
WA, WF = 6378137.0, 1 / 298.257223563
WB = WA * (1 - WF)


def vincenty_direct(lat, lon, az, s):
    """Kezdőpontból azimut (fok) és távolság (m) alapján a végpont (fok)."""
    phi1, a1 = math.radians(lat), math.radians(az)
    U1 = math.atan((1 - WF) * math.tan(phi1))
    s1 = math.atan2(math.tan(U1), math.cos(a1))
    sa = math.cos(U1) * math.sin(a1)
    c2a = 1 - sa * sa
    u2 = c2a * (WA * WA - WB * WB) / (WB * WB)
    A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    sig = s / (WB * A)
    for _ in range(100):
        c2sm = math.cos(2 * s1 + sig)
        ds = B * math.sin(sig) * (c2sm + B / 4 * (math.cos(sig) * (-1 + 2 * c2sm**2)
             - B / 6 * c2sm * (-3 + 4 * math.sin(sig)**2) * (-3 + 4 * c2sm**2)))
        new = s / (WB * A) + ds
        if abs(new - sig) < 1e-12:
            sig = new
            break
        sig = new
    c2sm = math.cos(2 * s1 + sig)
    tmp = math.sin(U1) * math.sin(sig) - math.cos(U1) * math.cos(sig) * math.cos(a1)
    phi2 = math.atan2(math.sin(U1) * math.cos(sig) + math.cos(U1) * math.sin(sig) * math.cos(a1),
                      (1 - WF) * math.sqrt(sa * sa + tmp * tmp))
    lam = math.atan2(math.sin(sig) * math.sin(a1),
                     math.cos(U1) * math.cos(sig) - math.sin(U1) * math.sin(sig) * math.cos(a1))
    C = WF / 16 * c2a * (4 + WF * (4 - 3 * c2a))
    L = lam - (1 - C) * WF * sa * (sig + C * math.sin(sig) * (c2sm + C * math.cos(sig) * (-1 + 2 * c2sm**2)))
    return math.degrees(phi2), lon + math.degrees(L)


def vincenty_inverse(lat1, lon1, lat2, lon2):
    """Geodéziai távolság (m) két pont között."""
    if (lat1, lon1) == (lat2, lon2):
        return 0.0
    U1 = math.atan((1 - WF) * math.tan(math.radians(lat1)))
    U2 = math.atan((1 - WF) * math.tan(math.radians(lat2)))
    L = math.radians(lon2 - lon1)
    lam = L
    for _ in range(200):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.hypot(math.cos(U2) * sl, math.cos(U1) * math.sin(U2) - math.sin(U1) * math.cos(U2) * cl)
        cs = math.sin(U1) * math.sin(U2) + math.cos(U1) * math.cos(U2) * cl
        sig = math.atan2(ss, cs)
        sa = math.cos(U1) * math.cos(U2) * sl / ss
        c2a = 1 - sa * sa
        c2sm = cs - 2 * math.sin(U1) * math.sin(U2) / c2a if c2a else 0.0
        C = WF / 16 * c2a * (4 + WF * (4 - 3 * c2a))
        new = L + (1 - C) * WF * sa * (sig + C * ss * (c2sm + C * cs * (-1 + 2 * c2sm**2)))
        if abs(new - lam) < 1e-12:
            lam = new
            break
        lam = new
    u2 = c2a * (WA * WA - WB * WB) / (WB * WB)
    A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    ds = B * ss * (c2sm + B / 4 * (cs * (-1 + 2 * c2sm**2) - B / 6 * c2sm * (-3 + 4 * ss**2) * (-3 + 4 * c2sm**2)))
    return WB * A * (sig - ds)



# --- Terület (GeoJSON) ---------------------------------------------------------
def _ring_area(r):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(r, r[1:])) / 2


def load_area(path):
    """GeoJSON -> a terület külső határgyűrűi [(lon, lat), ...].

    Egy (vagy néhány) poligon esetén a külső gyűrűket használja. Sok szomszédos
    poligonnál (pl. településhatárok) uniót képez: a két poligon által közösen
    használt határszakaszok kiesnek, a megmaradókból összeáll a külső határ.
    A lyukakat (pl. egy tó, ha nem tartozik településhez) a terület részének veszi.
    """
    d = json.load(open(path, encoding="utf-8"))
    geoms = []
    if d.get("type") == "FeatureCollection":
        geoms = [f["geometry"] for f in d["features"] if f.get("geometry")]
    elif d.get("type") == "Feature":
        geoms = [d["geometry"]]
    else:
        geoms = [d]
    polys = []
    for g in geoms:
        if g["type"] == "Polygon":
            polys.append(g["coordinates"])
        elif g["type"] == "MultiPolygon":
            polys.extend(g["coordinates"])
    if not polys:
        raise SystemExit("A GeoJSON-ban nincs Polygon/MultiPolygon.")
    if len(polys) <= 20:
        rings = [[(x, y) for x, y, *_ in p[0]] for p in polys]
    else:
        R = 7
        cnt = collections.Counter()
        for p in polys:
            for ring in p:
                pts = [(round(x, R), round(y, R)) for x, y, *_ in ring]
                for a, b in zip(pts, pts[1:]):
                    if a != b:
                        cnt[(a, b) if a < b else (b, a)] += 1
        single = [k for k, c in cnt.items() if c == 1]
        adj = collections.defaultdict(list)
        for a, b in single:
            adj[a].append(b)
            adj[b].append(a)
        used, rings = set(), []
        for a, b in single:
            if (a, b) in used:
                continue
            ring, cur = [a, b], b
            used.add((a, b))
            while cur != a:
                nxt = None
                for n in adj[cur]:
                    k = (cur, n) if cur < n else (n, cur)
                    if k not in used:
                        nxt = n
                        used.add(k)
                        break
                if nxt is None:
                    break
                ring.append(nxt)
                cur = nxt
            if len(ring) > 3:
                rings.append(ring)
    rings.sort(key=lambda r: -abs(_ring_area(r)))
    big = abs(_ring_area(rings[0]))
    rings = [r for r in rings if abs(_ring_area(r)) > 1e-4 * big]  # apró szilánkok ki
    return rings


def area_centroid(rings):
    r = rings[0]
    A = _ring_area(r)
    cx = sum((x1 + x2) * (x1 * y2 - x2 * y1) for (x1, y1), (x2, y2) in zip(r, r[1:])) / (6 * A)
    cy = sum((y1 + y2) * (x1 * y2 - x2 * y1) for (x1, y1), (x2, y2) in zip(r, r[1:])) / (6 * A)
    return cy, cx  # lat, lon


def point_in_rings(lon, lat, rings):
    """Páratlan-páros szabály gyűrűnként; bármelyik gyűrűn belül -> belül."""
    for r in rings:
        inside = False
        for (x1, y1), (x2, y2) in zip(r, r[1:]):
            if (y1 > lat) != (y2 > lat):
                if lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
                    inside = not inside
        if inside:
            return True
    return False


def dist_to_rings_km(lon, lat, rings):
    """Közelítő távolság (km) a határvonaltól, helyi síkvetületben."""
    kx = 111.32 * math.cos(math.radians(lat))
    ky = 110.57
    best = float("inf")
    for r in rings:
        for (x1, y1), (x2, y2) in zip(r, r[1:]):
            ax, ay = (x1 - lon) * kx, (y1 - lat) * ky
            bx, by = (x2 - lon) * kx, (y2 - lat) * ky
            dx, dy = bx - ax, by - ay
            L = dx * dx + dy * dy
            t = 0.0 if L == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / L))
            best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def simplify(ring, tol):
    """Douglas–Peucker egyszerűsítés (fokban), a megjelenítéshez."""
    if len(ring) < 4:
        return ring
    if ring[0] == ring[-1]:
        # zárt gyűrű: a kezdőponttól legtávolabbi pontnál kettévágva egyszerűsít
        x0, y0 = ring[0]
        m = max(range(len(ring)), key=lambda k: (ring[k][0] - x0) ** 2 + (ring[k][1] - y0) ** 2)
        return simplify(ring[:m + 1], tol)[:-1] + simplify(ring[m:], tol)
    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    stack = [(0, len(ring) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = ring[i], ring[j]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1e-12
        best, idx = 0.0, None
        for k in range(i + 1, j):
            x, y = ring[k]
            d = abs(dy * (x - x1) - dx * (y - y1)) / L
            if d > best:
                best, idx = d, k
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [p for p, k in zip(ring, keep) if k]


# --- Rács --------------------------------------------------------------------
def build_grid(lat, lon, h, edge, sides, rings, center, rot, maxdist=None, area=None, buffer_km=0.0):
    """Visszaad: állomáslista [(név, lat, lon, h)], élek [(i, j)]."""
    pts, edges = [], []  # pts: (név, x_kelet, y_észak) a síkban
    if sides == 6:
        if area:
            # annyi gyűrű, hogy a terület legtávolabbi pontját is elérje
            far = max(vincenty_inverse(lat, lon, y, x) for r in area for x, y in r[::max(1, len(r) // 400)])
            far += buffer_km * 1000 + edge
            rings = math.ceil(far / (edge * math.sqrt(3) / 2)) + 1
        elif maxdist:
            # annyi gyűrű, hogy a hatszög beírt köre is lefedje a max távolságot
            rings = math.ceil(maxdist / (edge * math.sqrt(3) / 2)) + 1
        if not center and rings != 1:
            raise SystemExit("--no-center csak --rings 1 mellett értelmes.")
        axial = [(q, r) for q in range(-rings, rings + 1) for r in range(-rings, rings + 1)
                 if max(abs(q), abs(r), abs(q + r)) <= rings]
        if maxdist:
            # csak a kezdőponttól max. távolságon belüli rácspontok (geodéziai távolság)
            axial = [(q, r) for q, r in axial
                     if math.hypot(edge * (q + r / 2), edge * r * math.sqrt(3) / 2) <= maxdist * (1 + 1e-9)]
        if not center:
            axial = [p for p in axial if p != (0, 0)]
        axial.sort(key=lambda p: (max(abs(p[0]), abs(p[1]), abs(p[0] + p[1])),
                                  math.atan2(p[1] * math.sqrt(3) / 2, p[0] + p[1] / 2)))
        for k, (q, r) in enumerate(axial):
            # síkkoordináták: az (1,0) irány az első csúcs iránya
            u = edge * (q + r / 2)
            v = edge * (r * math.sqrt(3) / 2)
            pts.append((f"S{k:03d}" if len(axial) > 100 else f"S{k:02d}", u, v))
        for i, (q1, r1) in enumerate(axial):
            for j, (q2, r2) in enumerate(axial):
                if j > i:
                    dq, dr = q2 - q1, r2 - r1
                    if (dq, dr) in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)):
                        edges.append((i, j))
    elif sides == 5:
        R = edge / (2 * math.sin(math.pi / 5))
        if center:
            pts.append(("S00", 0.0, 0.0))
        off = len(pts)
        for k in range(5):
            ang = 2 * math.pi * k / 5
            pts.append((f"S{k + off:02d}", R * math.cos(ang), R * math.sin(ang)))
        for k in range(5):
            edges.append((off + k, off + (k + 1) % 5))
            if center:
                edges.append((0, off + k))
    else:
        raise SystemExit("--sides csak 5 vagy 6 lehet.")

    stations = []
    for name, u, v in pts:
        # (u,v) sík: u az első csúcs iránya; azimut = rot + a polárszög (óramutatóval egyezően)
        s = math.hypot(u, v)
        if s < 1e-6:
            stations.append((name, lat, lon, h))
            continue
        az = (rot + math.degrees(math.atan2(v, u))) % 360
        la, lo = vincenty_direct(lat, lon, az, s)
        stations.append((name, la, lo, h))
    if area:
        keep = []
        for k, (_n, la, lo, _h) in enumerate(stations):
            if point_in_rings(lo, la, area) or (buffer_km > 0 and dist_to_rings_km(lo, la, area) <= buffer_km):
                keep.append(k)
        remap = {old: new for new, old in enumerate(keep)}
        w = 3 if len(keep) > 100 else 2
        stations = [(f"S{new:0{w}d}",) + stations[old][1:] for new, old in enumerate(keep)]
        edges = [(remap[i], remap[j]) for i, j in edges if i in remap and j in remap]
    return stations, edges



# --- Kézi állomáslista ---------------------------------------------------------
def read_stations(path):
    """Szöveges állomáslista: soronként  [név] szélesség hosszúság [magasság].

    Elválasztó lehet szóköz, tab, vessző vagy pontosvessző; '#' utáni rész
    megjegyzés. Szélesség/hosszúság tizedes fokban, magasság méterben
    (ellipszoidi; ha nincs megadva, 0). Név nélküli soroknál P001, P002, ...
    Ha az első sor fejléc (pl. 'name,lat,lon,h'), azt átugorja.
    """
    out, names = [], set()
    for ln, raw in enumerate(open(path, encoding="utf-8-sig"), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        tok = [t for t in line.replace(";", " ").replace(",", " ").replace("\t", " ").split(" ") if t]

        def isnum(t):
            try:
                float(t)
                return True
            except ValueError:
                return False
        if isnum(tok[0]):
            name, nums = f"P{len(out) + 1:03d}", tok
        else:
            name, nums = tok[0], tok[1:]
        if len(nums) < 2 or not all(isnum(t) for t in nums[:3]):
            if not out:
                continue  # fejléc
            raise SystemExit(f"{path}:{ln}: nem értelmezhető sor: {raw.strip()}")
        lat, lon = float(nums[0]), float(nums[1])
        h = float(nums[2]) if len(nums) > 2 else 0.0
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise SystemExit(f"{path}:{ln}: érvénytelen koordináta: {lat}, {lon}")
        if name in names:
            raise SystemExit(f"{path}:{ln}: ismétlődő állomásnév: {name}")
        names.add(name)
        out.append((name, lat, lon, h))
    if len(out) < 2:
        raise SystemExit(f"{path}: legalább 2 állomás kell.")
    return out


def _local_xy(stations):
    lat0 = sum(s[1] for s in stations) / len(stations)
    kx = 111.32 * math.cos(math.radians(lat0))
    return [(s[2] * kx, s[1] * 110.57) for s in stations]


def delaunay(pts):
    """Bowyer–Watson Delaunay-háromszögelés; visszaadja az éleket (i, j)."""
    n = len(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    d = max(max(xs) - min(xs), max(ys) - min(ys), 1.0) * 50
    P = list(pts) + [(mx - d, my - d), (mx + d, my - d), (mx, my + d)]
    tris = [(n, n + 1, n + 2)]

    def circ(t):
        (ax, ay), (bx, by), (cx, cy) = P[t[0]], P[t[1]], P[t[2]]
        D = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(D) < 1e-12:
            return (0.0, 0.0, float("inf"))
        ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / D
        uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / D
        return (ux, uy, (ax - ux) ** 2 + (ay - uy) ** 2)
    cc = {tris[0]: circ(tris[0])}
    for i in range(n):
        x, y = P[i]
        bad = [t for t in tris if (x - cc[t][0]) ** 2 + (y - cc[t][1]) ** 2 < cc[t][2] * (1 - 1e-12)]
        cnt = collections.Counter()
        for t in bad:
            for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                cnt[tuple(sorted(e))] += 1
        bs = set(bad)
        tris = [t for t in tris if t not in bs]
        for t in bad:
            del cc[t]
        for (a_, b_), c in cnt.items():
            if c == 1:
                t = (a_, b_, i)
                tris.append(t)
                cc[t] = circ(t)
    edges = set()
    for t in tris:
        for a_, b_ in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            if a_ < n and b_ < n:
                edges.add((min(a_, b_), max(a_, b_)))
    return sorted(edges)


def manual_neighbors(stations, mode, max_edge_km, pairs_path):
    """Szomszédság a kézi állomásokhoz.

    mode: 'delaunay' (alapért.), 'knn:K' (K legközelebbi), 'dist:KM' (adott
    távolságon belül mind), vagy --pairs fájl (soronként két állomásnév).
    --max-edge KM: az ennél hosszabb párok elhagyása.
    """
    n = len(stations)
    if pairs_path:
        idx = {s[0]: k for k, s in enumerate(stations)}
        edges = set()
        for ln, raw in enumerate(open(pairs_path, encoding="utf-8-sig"), 1):
            tok = [t for t in raw.split("#", 1)[0].replace(",", " ").replace(";", " ").split() if t]
            if not tok:
                continue
            if len(tok) < 2 or tok[0] not in idx or tok[1] not in idx:
                raise SystemExit(f"{pairs_path}:{ln}: ismeretlen állomás(ok): {raw.strip()}")
            i, j = idx[tok[0]], idx[tok[1]]
            if i != j:
                edges.add((min(i, j), max(i, j)))
        edges = sorted(edges)
    else:
        dist = lambda i, j: vincenty_inverse(stations[i][1], stations[i][2], stations[j][1], stations[j][2]) / 1000
        if mode == "delaunay":
            edges = delaunay(_local_xy(stations)) if n >= 3 else [(0, 1)]
        elif mode.startswith("knn:"):
            k = int(mode[4:])
            es = set()
            for i in range(n):
                near = sorted((dist(i, j), j) for j in range(n) if j != i)[:k]
                es.update((min(i, j), max(i, j)) for _d, j in near)
            edges = sorted(es)
        elif mode.startswith("dist:"):
            lim = float(mode[5:])
            edges = [(i, j) for i in range(n) for j in range(i + 1, n) if dist(i, j) <= lim]
        else:
            raise SystemExit("--neighbors: delaunay | knn:K | dist:KM")
    if max_edge_km:
        edges = [(i, j) for i, j in edges
                 if vincenty_inverse(stations[i][1], stations[i][2], stations[j][1], stations[j][2]) <= max_edge_km * 1000]
    return edges


# --- Almanach betöltés és pozíció tetszőleges időre ---------------------------
def load_almanac(path, include_bad):
    blob = open(path, "rb").read()
    alms, ini, leap = [], None, U.LEAP_GPS_UTC
    for cls, mid, p in U.ubx_frames(blob):
        if cls != 0x13:
            continue
        if mid == 0x40 and p[0] == 0x10 and len(p) >= 24:
            (_t, _v, _r, ls, yr, mo, dy, hh, mm, ss, _x, _ns) = struct.unpack_from("<BBBbHBBBBBBI", p)
            ini = datetime(yr, mo, dy, hh, mm, ss, tzinfo=timezone.utc)
            if ls not in (-128, 0):
                leap = ls
        elif p and p[0] == 0x02:
            dec = {0x00: lambda q: U.dec_gps_like(q, "GPS"), 0x05: lambda q: U.dec_gps_like(q, "QZS"),
                   0x02: U.dec_gal, 0x03: U.dec_bds, 0x06: U.dec_glo}.get(mid)
            if dec:
                alms.append(dec(p))
    t_ref = ini or datetime.now(timezone.utc)
    kept, dropped = [], []
    for a in alms:
        age = sat_state(a, t_ref, leap)[1]
        if a["sys"] == "GLO":
            healthy = a["health"] == 1
        elif a["sys"] == "BDS":
            healthy = True
        else:
            healthy = a["health"] == 0
        if a["sys"] == "BDS" and not (20000e3 < a["sqrta"] ** 2 < 45000e3):
            healthy = False  # fizikailag nem BeiDou-pálya (pl. C17 tesztadat)
        stale = abs(age) > 7 * 86400
        if include_bad or (healthy and not stale):
            kept.append(a)
        else:
            dropped.append(a["prn"])
    return kept, dropped, ini, leap


def sat_state(a, t, leap):
    """ECEF (m) és az almanach kora (s) a t időpontban."""
    s = a["sys"]
    if s == "GLO":
        x, y, z, _clk, age = U.pos_glo(a, t)
        return (x, y, z), age
    gw, gtow = U.gps_week_tow(t, leap)
    if s in ("GPS", "QZS"):
        cw, tow, mod = gw, gtow, 256
    elif s == "GAL":
        cw, tow, mod = gw - U.GST_WEEK_OFFSET, gtow, 4
    else:
        bs = gw * 604800 + gtow - U.BDT_GPST
        cw, tow, mod = int(bs // 604800) - U.BDS_WEEK_OFFSET, bs % 604800, 256
    wa = U.full_week(cw, a["wna"], mod)
    tk = (cw - wa) * 604800 + (tow - a["toa"])
    x, y, z, _clk = U.pos_kepler(a, tk)
    return (x, y, z), tk


# --- Fő program --------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("almanac", help="UBX fájl MGA-*-ALM üzenetekkel")
    ap.add_argument("--lat", type=float, help="kezdőpont szélesség [fok] (--area mellett elhagyható: a terület középpontja)")
    ap.add_argument("--lon", type=float, help="kezdőpont hosszúság [fok]")
    ap.add_argument("--h", type=float, default=0.0, help="ellipszoidi magasság [m]")
    ap.add_argument("--edge", type=float, help="élhossz [km] (rácshoz kötelező)")
    ap.add_argument("--stations", help="kézi állomáslista (txt/csv): soronként [név] lat lon [h]; a rács helyett")
    ap.add_argument("--neighbors", default="delaunay",
                    help="kézi állomások szomszédsága: delaunay (alapért.) | knn:K | dist:KM")
    ap.add_argument("--max-edge", type=float, help="kézi állomásoknál az ennél hosszabb párok elhagyása [km]")
    ap.add_argument("--pairs", help="kézi szomszédpárok fájlja: soronként két állomásnév")
    ap.add_argument("--sides", type=int, default=6, choices=(5, 6))
    ap.add_argument("--rings", type=int, default=1, help="gyűrűk száma (csak --sides 6)")
    ap.add_argument("--max-dist", type=float,
                    help="terület lefedése: a kezdőponttól ennyi km-en belüli összes rácspont "
                         "(csak --sides 6; a --rings értékét felülírja)")
    ap.add_argument("--area", help="GeoJSON poligon (pl. országhatár): az ezen belüli rácspontok lesznek állomások")
    ap.add_argument("--border-buffer", type=float, default=0.0,
                    help="--area mellett: a határon kívül ennyi km-en belüli rácspontokat is megtartja")
    ap.add_argument("--no-azel", action="store_true",
                    help="ne írja ki az azel.csv-t (sok állomásnál nagy fájl)")
    ap.add_argument("--no-center", action="store_true", help="a kezdőpont nem állomás")
    ap.add_argument("--rot", type=float, default=0.0, help="rács elforgatása [fok]")
    ap.add_argument("--start", help="kezdő idő UTC, pl. '2026-10-21 00:00' (alapért.: letöltés ideje)")
    ap.add_argument("--days", type=float, default=5.0)
    ap.add_argument("--step", type=float, default=15.0, help="lépésköz [perc]")
    ap.add_argument("--mask", type=float, default=10.0, help="elevációs maszk [fok]")
    ap.add_argument("--min-common", type=int, default=4,
                    help="küszöb: ennyi közös műhold kell rendszerenként (summary pct_ge oszlop)")
    ap.add_argument("--systems", default="GPS,GAL,GLO,BDS,QZS")
    ap.add_argument("--include-bad", action="store_true",
                    help="az elavult/hibás almanachú műholdakat is számolja")
    ap.add_argument("--html", nargs="?", const="grid_view.html",
                    help="interaktív időbeli ábra (HTML) készítése az --out mappába")
    ap.add_argument("--out", default="grid_out")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    systems = [s.strip().upper() for s in a.systems.split(",")]

    # 1) állomások: kézi lista vagy rács
    area = load_area(a.area) if a.area else None
    if a.stations:
        stations = read_stations(a.stations)
        edges = manual_neighbors(stations, a.neighbors, a.max_edge, a.pairs)
        print(f"Kézi állomások: {len(stations)} db ({a.stations}), szomszédság: "
              f"{'pár-fájl ' + a.pairs if a.pairs else a.neighbors}")
        if area:
            out_area = [s_[0] for s_ in stations if not point_in_rings(s_[2], s_[1], area)]
            if out_area:
                print(f"Figyelem, a területen kívül esik: {', '.join(out_area)} (a számításban benne marad)")
    else:
        if a.edge is None:
            raise SystemExit("Add meg a rács élhosszát (--edge) vagy egy állomáslistát (--stations).")
        if (area or a.max_dist) and a.sides != 6:
            raise SystemExit("--area és --max-dist csak --sides 6 mellett használható.")
        if a.lat is None or a.lon is None:
            if not area:
                raise SystemExit("Add meg a --lat/--lon kezdőpontot (vagy egy --area GeoJSON-t).")
            a.lat, a.lon = area_centroid(area)
            print(f"Kezdőpont: a terület középpontja ({a.lat:.5f}, {a.lon:.5f})")
        stations, edges = build_grid(a.lat, a.lon, a.h, a.edge * 1000, a.sides, a.rings,
                                     not a.no_center, a.rot,
                                     a.max_dist * 1000 if a.max_dist else None,
                                     area, a.border_buffer)
    if not edges:
        raise SystemExit("Nincs szomszédos állomáspár (túl nagy élhossz / túl kicsi --max-edge?).")
    with open(os.path.join(a.out, "stations.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["station", "lat_deg", "lon_deg", "h_m"])
        for s in stations:
            w.writerow([s[0], f"{s[1]:.8f}", f"{s[2]:.8f}", s[3]])
    edge_rows = []
    for i, j in edges:
        d = vincenty_inverse(stations[i][1], stations[i][2], stations[j][1], stations[j][2])
        edge_rows.append((f"{stations[i][0]}-{stations[j][0]}", i, j, d))
    with open(os.path.join(a.out, "edges.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pair", "station_a", "station_b", "dist_km"])
        for name, i, j, d in edge_rows:
            w.writerow([name, stations[i][0], stations[j][0], f"{d / 1000:.4f}"])
    dists = [d / 1000 for *_x, d in edge_rows]
    print(f"Állomások: {len(stations)}, {len(edges)} szomszédos pár, "
          f"élhossz {min(dists):.3f}–{max(dists):.3f} km")

    # 2) pályaszámítás
    alms, dropped, ini, leap = load_almanac(a.almanac, a.include_bad)
    alms = [x for x in alms if x["sys"] in systems]
    systems = [sy for sy in systems if any(x["sys"] == sy for x in alms)]
    t0 = U.parse_time(a.start) if a.start else (ini or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    n_ep = int(round(a.days * 24 * 60 / a.step)) + 1
    epochs = [t0 + timedelta(minutes=a.step * k) for k in range(n_ep)]
    print(f"Műholdak: {len(alms)}  (kihagyva elavult/hibás almanach miatt: {', '.join(dropped) or '-'})")
    print(f"Időszak: {epochs[0]:%Y-%m-%d %H:%M} – {epochs[-1]:%Y-%m-%d %H:%M} UTC, "
          f"{n_ep} epoch, {a.step:g} perces lépés, maszk {a.mask:g}°")

    # állomásonként ECEF + helyi kelet/észak/fel egységvektorok (gyors az/el)
    rx = []
    for _n, la, lo, hh in stations:
        X = U.geodetic_to_ecef(la, lo, hh)
        sl, cl = math.sin(math.radians(la)), math.cos(math.radians(la))
        so, co = math.sin(math.radians(lo)), math.cos(math.radians(lo))
        rx.append((X, (-so, co, 0.0), (-sl * co, -sl * so, cl), (cl * co, cl * so, sl)))
    sin_mask = math.sin(math.radians(a.mask))
    sat_sys = [al["sys"] for al in alms]
    sat_prn = [al["prn"] for al in alms]

    # 3) azimut/eleváció és közös műholdak
    stats = {(e[0], s): [] for e in edge_rows for s in systems}
    sat_track = []  # epochonként a műholdak ECEF-je (a HTML-hez)
    f_az = None if a.no_azel else open(os.path.join(a.out, "azel.csv"), "w", newline="")
    f_cm = open(os.path.join(a.out, "common.csv"), "w", newline="")
    w_az = csv.writer(f_az) if f_az else None
    w_cm = csv.writer(f_cm)
    if w_az:
        w_az.writerow(["epoch_utc", "station", "prn", "sys", "az_deg", "el_deg"])
    w_cm.writerow(["epoch_utc", "pair", "sys", "common", "visible_a", "visible_b", "common_prns"])
    for t in epochs:
        ts = t.strftime("%Y-%m-%d %H:%M")
        pos = [sat_state(al, t, leap)[0] for al in alms]
        sat_track.append(pos)
        vis = []  # állomásonként: {sys: set(prn)}
        for st, (X, E, N, Up) in zip(stations, rx):
            v = {s: set() for s in systems}
            for k, (sx, sy_, sz) in enumerate(pos):
                dx, dy, dz = sx - X[0], sy_ - X[1], sz - X[2]
                u = dx * Up[0] + dy * Up[1] + dz * Up[2]
                rng = math.sqrt(dx * dx + dy * dy + dz * dz)
                if u >= rng * sin_mask:
                    v[sat_sys[k]].add(sat_prn[k])
                    if w_az:
                        e = dx * E[0] + dy * E[1]
                        n = dx * N[0] + dy * N[1] + dz * N[2]
                        w_az.writerow([ts, st[0], sat_prn[k], sat_sys[k],
                                       f"{math.degrees(math.atan2(e, n)) % 360:.2f}",
                                       f"{math.degrees(math.asin(u / rng)):.2f}"])
            vis.append(v)
        for name, i, j, _d in edge_rows:
            for sy in systems:
                c = vis[i][sy] & vis[j][sy]
                w_cm.writerow([ts, name, sy, len(c), len(vis[i][sy]), len(vis[j][sy]),
                               " ".join(sorted(c))])
                stats[(name, sy)].append(len(c))
    if f_az:
        f_az.close()
    f_cm.close()

    # összefoglaló
    thr = a.min_common
    tot = {name: [sum(stats[(name, sy)][k] for sy in systems) for k in range(n_ep)]
           for name, *_r in edge_rows}
    with open(os.path.join(a.out, "summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pair", "sys", "min", "mean", "max", f"pct_ge{thr}"])
        for (name, sy), v in stats.items():
            w.writerow([name, sy, min(v), f"{sum(v) / len(v):.2f}", max(v),
                        f"{100 * sum(1 for x in v if x >= thr) / len(v):.1f}"])
        for name, v in tot.items():
            w.writerow([name, "ALL", min(v), f"{sum(v) / len(v):.2f}", max(v),
                        f"{100 * sum(1 for x in v if x >= thr) / len(v):.1f}"])

    print("\nKözös műholdak szomszédos párok között (min / átlag / max, minden párra összesítve):")
    for sy in systems + ["ALL"]:
        if sy == "ALL":
            vals = [x for name in tot for x in tot[name]]
        else:
            vals = [x for (name, s2), v in stats.items() if s2 == sy for x in v]
        if vals:
            print(f"  {sy:4} {min(vals):3d} / {sum(vals) / len(vals):5.1f} / {max(vals):3d}")
    worst = min(tot, key=lambda n: min(tot[n]))
    print(f"Legkevesebb közös műhold: {worst} pár, {min(tot[worst])} db")
    outs = ["stations.csv", "edges.csv"] + ([] if a.no_azel else ["azel.csv"]) + ["common.csv", "summary.csv"]

    if a.html:
        import grid_html
        outline = [simplify(r, 0.003) for r in area] if area else None
        path = os.path.join(a.out, a.html)
        grid_html.write_html(path, stations=stations, edge_rows=edge_rows, sat_prn=sat_prn,
                             sat_sys=sat_sys, sat_track=sat_track, epochs=epochs,
                             step_min=a.step, mask=a.mask, threshold=thr, outline=outline,
                             edge_km=None if a.stations else a.edge, dropped=dropped)
        outs.append(a.html)
        print(f"HTML: {path}")
    print(f"\nKimenetek ({a.out}/): {', '.join(outs)}")


if __name__ == "__main__":
    main()
