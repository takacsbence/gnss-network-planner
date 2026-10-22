# GNSS almanac tools

Three tools that work as a chain:

1. **`ubx_alm.py`** decodes the u-blox AssistNow almanac and computes satellite positions.
2. **`grid_vis.py`** builds a set of stations (a hexagonal grid or your own list), propagates the orbits over a time window, and counts the satellites each pair of neighbouring stations can both see, per constellation.
3. **`grid_html.py`** writes an interactive HTML page that shows the results over time. You do not run it directly: `grid_vis.py` calls it when you pass `--html`.

All three need only Python 3; see *Requirements and installation* below. Keep the files in the same folder.

```
ubx_alm.py         almanac decoder and orbit computation (also used as a library)
grid_vis.py        stations, propagation, visibility and common satellites
grid_html.py       HTML visualisation (used by grid_vis.py --html)
assistnow_alm.py   optional: downloads the almanac from AssistNow (needs a receiver and pyserial + requests)
```

---

## Requirements and installation

| Component | Needs | Install |
|---|---|---|
| `ubx_alm.py`, `grid_vis.py`, `grid_html.py` | Python 3.8 or newer (tested with 3.12–3.13); standard library only | nothing beyond Python |
| HTML page | Any current browser (Chrome, Firefox, Edge, Safari); works offline | nothing |
| `assistnow_alm.py` (optional download) | `pyserial`, `requests`, a u-blox receiver on USB/UART, Internet access | see below |

Check your Python version:

```bash
python3 --version
```

Install Python if it is missing:

- **Debian/Ubuntu:** `sudo apt install python3`
- **Windows/macOS:** download from python.org, then use `python` or `py` in place of `python3` in the examples below.

The packages for the optional download script can come from the system packages or a virtual environment.

**Debian/Ubuntu system packages:**

```bash
sudo apt install python3-serial python3-requests
```

**Any OS, using a virtual environment.** This is also the way around the `externally-managed-environment` pip error on Debian/Ubuntu:

```bash
python3 -m venv ~/venv-gnss
~/venv-gnss/bin/pip install pyserial requests
~/venv-gnss/bin/python assistnow_alm.py -z <ZTP-TOKEN> -P /dev/ttyACM0
```

On Linux, if opening the serial port fails with `Permission denied`, add yourself to the `dialout` group, then log out and back in:

```bash
sudo usermod -aG dialout $USER
```

---

## 1. Getting the almanac

The input is a binary UBX file containing `UBX-MGA-*-ALM` messages (GPS, Galileo, BeiDou, QZSS, GLONASS), as returned by the AssistNow `ualm` data type.

With a Thingstream ZTP device profile and a u-blox receiver (for example a ZED-F9P):

```bash
# First run: the receiver must be connected. Its ID is read and cached in assistnow_device.json.
python3 assistnow_alm.py -z <ZTP-TOKEN> -P /dev/ttyACM0

# Later runs: no receiver needed, the cached credentials are used.
python3 assistnow_alm.py -z <ZTP-TOKEN> -o alm.ubx
```

AssistNow limits the number of requests per device. If you get `403002 usage limit`, wait for the limit to reset. Downloading once a day is plenty for almanac work.

---

## 2. `ubx_alm.py`: decode and compute positions

```bash
# Decode everything and compute ECEF positions at the download time
# (taken from MGA-INI-TIME-UTC in the file)
python3 ubx_alm.py alm.ubx

# Positions at a given UTC time, plus azimuth/elevation from a receiver
# position (lat, lon, ellipsoidal height in m). Only satellites above the horizon are listed.
python3 ubx_alm.py alm.ubx --time "2026-10-21 18:00:00" --pos 47.4979,19.0402,150

# Include satellites below the horizon, and write the CSVs to a folder
python3 ubx_alm.py alm.ubx --pos 47.5,19.0,150 --all --csv-prefix out/
```

**Outputs**

| File | Content |
|---|---|
| `alm_params.csv` | Every decoded almanac field per satellite, scaled to SI units and radians |
| `alm_positions.csv` | ECEF position (m), clock offset (µs), almanac age (h) and status; azimuth/elevation when `--pos` is given |

**Notes**

- **Algorithms.** GPS, Galileo, BeiDou and QZSS use the standard Keplerian almanac algorithm (IS-GPS-200). GLONASS uses the simplified ICD algorithm with J2 secular terms and no short-period corrections, which is accurate to a few km.
- **Week numbers.** Truncated almanac week numbers (8-bit, or 2-bit for Galileo) are resolved to the full week closest to the computation time.
- **Status column.** `hibás` means the almanac health flag reports a problem. `ELAVULT` means the almanac is older than 7 days.
- **BeiDou.** The `MGA-BDS-ALM` message has no health field, so BeiDou status shows `–`.

---

## 3. `grid_vis.py`: stations, propagation and common satellites

### Station sources (choose one)

**A) Hexagonal grid.** All neighbour distances equal `--edge`.

```bash
# 7 stations: a centre point plus one ring, 20 km edges
python3 grid_vis.py alm.ubx --lat 47.0 --lon 19.0 --h 150 --edge 20 --rings 1

# Cover a circle of 300 km radius around the start point
python3 grid_vis.py alm.ubx --lat 47.0 --lon 19.0 --edge 50 --max-dist 300 --no-azel

# Cover a country from a GeoJSON polygon. Without --lat/--lon the grid starts at the polygon centroid.
python3 grid_vis.py alm.ubx --area hu.json --edge 20 --no-azel --html

# Also keep grid points up to 10 km outside the border
python3 grid_vis.py alm.ubx --area hu.json --edge 20 --border-buffer 10 --html

# A single pentagon around the start point
python3 grid_vis.py alm.ubx --lat 47.0 --lon 19.0 --edge 50 --sides 5
```

**About `--area`.** It accepts a single country outline or a file of many adjacent polygons, such as municipality boundaries. In the second case the polygons are merged automatically. Holes are treated as part of the area, so a lake still gets covered.

**B) Your own station list** with `--stations`. Each line is `[name] lat lon [height_m]`, in decimal degrees with ellipsoidal height. Fields can be separated by spaces, tabs, commas or semicolons. A `#` starts a comment, and a header line is skipped.

```
# name  lat       lon       h
BUTE    47.48090  19.05650  180
PENC    47.78960  19.28150  290
SZEG    46.25300  20.14800   80
```

```bash
# Neighbours by Delaunay triangulation (the default). Drop pairs longer than 200 km.
python3 grid_vis.py alm.ubx --stations allomasok.txt --max-edge 200 --area hu.json --html --no-azel

# Each station paired with its 4 nearest stations
python3 grid_vis.py alm.ubx --stations allomasok.txt --neighbors knn:4

# Every pair closer than 80 km
python3 grid_vis.py alm.ubx --stations allomasok.txt --neighbors dist:80

# Explicit pairs: one pair of station names per line
python3 grid_vis.py alm.ubx --stations allomasok.txt --pairs pairs.txt
```

**Notes on station lists**

- **Delaunay edges.** Delaunay can add long edges along the outer boundary of the network. Use `--max-edge` to remove them.
- **`--area` here.** With `--stations`, the `--area` polygon is only drawn as the map background. Stations outside it get a warning but stay in the calculation.

### Time window and visibility

| Option | Default | Meaning |
|---|---|---|
| `--start "2026-10-21 00:00"` | download time | Start time (UTC) |
| `--days 5` | 5 | Length of the window |
| `--step 15` | 15 | Time step in minutes |
| `--mask 10` | 10 | Elevation mask in degrees |
| `--min-common 4` | 4 | Threshold used for the `pct_ge` column in `summary.csv` |
| `--systems GPS,GAL,GLO,BDS,QZS` | all | Constellations to use |
| `--include-bad` | off | Keep stale or unhealthy almanacs (excluded by default) |
| `--out grid_out` | `grid_out` | Output folder |
| `--no-azel` | off | Skip `azel.csv`, which gets large for big grids |
| `--html [name]` | off | Write the interactive page (default name `grid_view.html`) |

A satellite counts as **common** to a pair of stations when it is above the mask at both stations at the same epoch. Terrain obstruction is not modelled.

### Outputs (in `--out`)

| File | Content |
|---|---|
| `stations.csv` | name, lat, lon, h |
| `edges.csv` | Neighbouring pairs with their geodesic (WGS84) distance |
| `azel.csv` | epoch, station, PRN, azimuth, elevation, for satellites above the mask |
| `common.csv` | epoch, pair, constellation, common count, visible count at each end, list of common PRNs |
| `summary.csv` | Per pair and constellation (and `ALL`): min / mean / max common count, and the % of epochs at or above the threshold |
| `grid_view.html` | Interactive visualisation (with `--html`) |

Example full run: Hungary, 20 km grid, 5 days at 15-minute steps. This gives 272 stations and 738 pairs, and takes about 10 s.

```bash
python3 grid_vis.py alm.ubx --area hu.json --edge 20 --days 5 --step 15 --mask 10 --no-azel --html
```

---

## 4. The HTML page

`grid_view.html` is one self-contained file that you open in any browser, with no server needed. It contains the satellite positions for every epoch. The browser recomputes visibility and common counts with the same method as the Python code, so the mask and the threshold can be changed on the page.

- **Constellation selector.** Choose All, GPS, Galileo, GLONASS or BeiDou.
- **Elevation mask slider** and **threshold** (the minimum number of common satellites). Changing either recomputes everything in about 0.1 s for a few hundred stations.
- **Time slider and Play button.** The arrow keys step one epoch at a time, and Space plays or pauses.
- **Map.** Each edge is coloured by its common-satellite count relative to the threshold: red below, grey at the threshold, blue above. Hovering over an edge shows the counts per constellation and the common PRNs.
- **Clicking a station** shows:
  - a sky plot with the azimuth and elevation of every satellite (hollow markers are below the mask);
  - the common count for each neighbour;
  - the number of visible satellites per constellation.
- **Time-series charts.**
  - The first shows the min–max band and the mean common count over all pairs, plus the selected station's worst neighbour.
  - The second shows the share of pairs below the threshold.
  - Clicking either chart jumps to that time.
- **Readout cards.** The current minimum, current mean, number of pairs below the threshold, and the period minimum.
- **Dark mode.** The page follows the system light/dark setting.

---

## Accuracy and limitations

- **Almanac accuracy.** Almanac orbits are accurate to roughly 1–5 km over several days. That is good for visibility planning, but not for positioning.
- **Filtered almanacs.** Almanacs older than 7 days, unhealthy satellites, and physically impossible BeiDou orbits are left out by default. The run summary lists them.
- **Grid edge lengths.** The grid is built in an azimuthal-equidistant plane around the start point. Distances from the start point are exact. Edge lengths far from it can be a few metres short; for example, 14 m at 300 km with 50 km edges. `edges.csv` always reports the measured geodesic lengths.
- **Time scales.** Times are UTC. GPS–UTC leap seconds are taken from the file (default 18 s).
