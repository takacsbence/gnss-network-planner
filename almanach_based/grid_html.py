"""
Interaktív HTML nézet a grid_vis.py eredményeihez.

A műholdak epochonkénti ECEF pozíciója kerül a fájlba, a láthatóságot és a
közös műholdak számát a böngésző számolja újra ugyanazzal a módszerrel, így az
elevációs maszk és a küszöb a lapon is állítható. Külső könyvtár nem kell.
"""
import base64
import json
import struct

SYS_LIST = ["GPS", "GAL", "GLO", "BDS", "QZS"]


def write_html(path, *, stations, edge_rows, sat_prn, sat_sys, sat_track, epochs,
               step_min, mask, threshold, outline, edge_km, dropped):
    flat = [c for ep in sat_track for p in ep for c in p]
    track_b64 = base64.b64encode(struct.pack(f"<{len(flat)}f", *flat)).decode("ascii")
    data = {
        "stations": [[s[0], round(s[1], 7), round(s[2], 7), s[3]] for s in stations],
        "edges": [[i, j, round(d / 1000, 3)] for _n, i, j, d in edge_rows],
        "satPrn": sat_prn,
        "satSys": [SYS_LIST.index(s) for s in sat_sys],
        "t0": epochs[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stepMin": step_min,
        "nEp": len(epochs),
        "mask": mask,
        "threshold": threshold,
        "edgeKm": edge_km,
        "dropped": dropped,
        "outline": [[[round(x, 4), round(y, 4)] for x, y in r] for r in outline] if outline else None,
    }
    html = TEMPLATE.replace("/*__DATA__*/", json.dumps(data, separators=(",", ":"))) \
                   .replace("__TRACK__", track_b64)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


TEMPLATE = r"""<!doctype html>
<html lang="hu">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GNSS állomásrács</title>
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --surface-2: #f3f2ee;
  --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --ring: rgba(11,11,11,0.10);
  --land: #f1f0ea; --land-line: #c3c2b7;
  --s0: #2a78d6; --s1: #eb6834; --s2: #1baf7a; --s3: #eda100; --s4: #e87ba4; --sel: #6250d6;
  --d-3: #b8312f; --d-2: #e34948; --d-1: #f0a09d; --d0: #a9a8a1;
  --d1: #86b6ef; --d2: #3987e5; --d3: #1c5cab;
  --crit: #d03b3b; --accent: #2a78d6;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --surface-2: #232321;
    --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10);
    --land: #20201e; --land-line: #4a4945;
    --s0: #3987e5; --s1: #d95926; --s2: #199e70; --s3: #c98500; --s4: #d55181; --sel: #9085e9;
    --d-3: #e66767; --d-2: #d04a4a; --d-1: #8f3a38; --d0: #6b6a65;
    --d1: #2f5f99; --d2: #3987e5; --d3: #86b6ef;
    --crit: #e66767; --accent: #3987e5;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --surface-2: #232321;
  --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10);
  --land: #20201e; --land-line: #4a4945;
  --s0: #3987e5; --s1: #d95926; --s2: #199e70; --s3: #c98500; --s4: #d55181; --sel: #9085e9;
  --d-3: #e66767; --d-2: #d04a4a; --d-1: #8f3a38; --d0: #6b6a65;
  --d1: #2f5f99; --d2: #3987e5; --d3: #86b6ef;
  --crit: #e66767; --accent: #3987e5;
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body { background: var(--page); color: var(--ink); font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width: 1320px; margin: 0 auto; padding: 20px 16px 40px; }
header h1 { font-size: 20px; font-weight: 650; margin: 0 0 2px; letter-spacing: -0.01em; }
header p { margin: 0; color: var(--ink-2); font-size: 13px; }
.card { background: var(--surface); border: 1px solid var(--ring); border-radius: 12px; }
.bar { display: flex; flex-wrap: wrap; gap: 12px 20px; align-items: center; padding: 12px 14px; margin-top: 14px; }
.bar label { color: var(--ink-2); font-size: 12px; display: flex; align-items: center; gap: 8px; }
.seg { display: inline-flex; background: var(--surface-2); border-radius: 8px; padding: 2px; gap: 2px; flex-wrap: wrap; }
.seg button { border: 0; background: transparent; color: var(--ink-2); font: inherit; font-size: 13px; padding: 5px 10px; border-radius: 6px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.seg button[aria-pressed="true"] { background: var(--surface); color: var(--ink); box-shadow: 0 0 0 1px var(--ring); font-weight: 600; }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; }
input[type=range] { accent-color: var(--accent); }
.num { width: 54px; font: inherit; padding: 3px 6px; border-radius: 6px; border: 1px solid var(--ring); background: var(--surface); color: var(--ink); }
.timebar { display: flex; align-items: center; gap: 12px; padding: 10px 14px; margin-top: 10px; }
.timebar input[type=range] { flex: 1; min-width: 0; }
.play { width: 34px; height: 34px; border-radius: 50%; border: 1px solid var(--ring); background: var(--surface-2); color: var(--ink); cursor: pointer; font-size: 13px; flex: none; }
.tlabel { font-variant-numeric: tabular-nums; font-size: 13px; white-space: nowrap; }
.tlabel small { color: var(--muted); }
select { font: inherit; font-size: 12px; background: var(--surface); color: var(--ink); border: 1px solid var(--ring); border-radius: 6px; padding: 3px; }
.main { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 12px; margin-top: 12px; }
@media (max-width: 900px) { .main { grid-template-columns: minmax(0, 1fr); } .tlabel small { display: none; } }
.mapcard { padding: 10px; position: relative; }
#map { width: 100%; height: auto; display: block; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; align-items: center; font-size: 12px; color: var(--ink-2); padding: 4px 6px 2px; }
.legend .sw { display: inline-block; width: 18px; height: 3px; border-radius: 2px; vertical-align: middle; margin-right: 5px; }
.side { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--ring); border-radius: 12px; overflow: hidden; border: 1px solid var(--ring); }
.kpi { background: var(--surface); padding: 10px 12px; }
.kpi .k { font-size: 12px; color: var(--ink-2); }
.kpi .v { font-size: 22px; font-weight: 650; line-height: 1.2; }
.kpi .s { font-size: 12px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.panel { padding: 12px 14px; }
.panel h2 { font-size: 14px; margin: 0 0 2px; font-weight: 650; }
.panel .sub { font-size: 12px; color: var(--muted); margin-bottom: 8px; }
#sky { width: 100%; max-width: 300px; display: block; margin: 0 auto; }
table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
td, th { padding: 3px 4px; text-align: left; border-bottom: 1px solid var(--grid); }
th { color: var(--muted); font-weight: 500; }
td.n { text-align: right; font-variant-numeric: tabular-nums; }
.chip { display: inline-block; min-width: 24px; text-align: center; border-radius: 5px; padding: 0 5px; font-variant-numeric: tabular-nums; font-weight: 600; color: var(--ink); }
.charts { margin-top: 12px; padding: 12px 14px; }
.charts h2 { font-size: 14px; margin: 0; font-weight: 650; }
.charts .sub { font-size: 12px; color: var(--muted); margin: 2px 0 6px; }
.chartleg { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 12px; color: var(--ink-2); margin-bottom: 4px; }
.chartleg .sw { display: inline-block; width: 16px; height: 8px; border-radius: 2px; vertical-align: middle; margin-right: 5px; }
#ts, #low { width: 100%; height: auto; display: block; }
.mapcard { display: flex; flex-direction: column; justify-content: center; }
svg text { fill: var(--muted); font-size: 11px; font-family: inherit; }
.tip { position: fixed; pointer-events: none; background: var(--surface); color: var(--ink); border: 1px solid var(--ring); box-shadow: 0 4px 16px rgba(0,0,0,.12); border-radius: 8px; padding: 7px 9px; font-size: 12px; line-height: 1.4; max-width: 280px; z-index: 10; display: none; }
.tip b { font-weight: 650; }
.tip .m { color: var(--muted); }
.note { font-size: 12px; color: var(--muted); margin-top: 14px; }
.hint { font-size: 12px; color: var(--muted); }
#busy { font-size: 12px; color: var(--muted); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>GNSS állomásrács – közös műholdak időben</h1>
    <p id="meta"></p>
  </header>

  <div class="card bar">
    <div class="seg" id="sysSeg" role="group" aria-label="Rendszer"></div>
    <label>Elevációs maszk <input type="range" id="mask" min="0" max="40" step="1"> <span id="maskV" class="tlabel"></span></label>
    <label>Küszöb (min. közös) <input type="number" class="num" id="thr" min="0" max="60" step="1"></label>
    <span id="busy"></span>
  </div>

  <div class="card timebar">
    <button class="play" id="play" aria-label="Lejátszás">▶</button>
    <input type="range" id="time" min="0" step="1" aria-label="Időpont">
    <select id="speed" aria-label="Sebesség"><option value="250">1×</option><option value="100" selected>2×</option><option value="40">5×</option></select>
    <span class="tlabel" id="tLabel"></span>
  </div>

  <div class="main">
    <div class="card mapcard">
      <svg id="map" role="img" aria-label="Állomásrács térkép"></svg>
      <div class="legend" id="mapLegend"></div>
    </div>
    <div class="side">
      <div class="kpis" id="kpis"></div>
      <div class="card panel">
        <h2 id="stTitle">Állomás</h2>
        <div class="sub" id="stSub">Kattints egy állomásra a térképen.</div>
        <svg id="sky" viewBox="-130 -130 260 260" role="img" aria-label="Égbolt-ábra"></svg>
        <div class="legend" id="skyLegend" style="justify-content:center"></div>
        <table id="stTable"></table>
      </div>
    </div>
  </div>

  <div class="card charts">
    <h2 id="tsTitle">Közös műholdak a szomszédos párok között</h2>
    <div class="sub">Minden szomszédos pár epochonként; a sáv a legkevesebb és a legtöbb közös műhold közötti tartomány. Kattints a grafikonra az időpont kiválasztásához.</div>
    <div class="chartleg" id="tsLeg"></div>
    <svg id="ts" role="img" aria-label="Közös műholdak időbeli alakulása"></svg>
    <h2 style="margin-top:14px">Küszöb alatti párok aránya</h2>
    <div class="sub" id="lowSub"></div>
    <svg id="low" role="img" aria-label="Küszöb alatti párok aránya"></svg>
  </div>
  <p class="note" id="foot"></p>
</div>
<div class="tip" id="tip"></div>

<script id="data" type="application/json">/*__DATA__*/</script>
<script>
"use strict";
const D = JSON.parse(document.getElementById("data").textContent);
const TRACK = (() => {
  const bin = atob("__TRACK__");
  const buf = new ArrayBuffer(bin.length);
  const u8 = new Uint8Array(buf);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  return new Float32Array(buf);
})();
const SYS = [
  { id: "GPS", name: "GPS" }, { id: "GAL", name: "Galileo" }, { id: "GLO", name: "GLONASS" },
  { id: "BDS", name: "BeiDou" }, { id: "QZS", name: "QZSS" }];
const ALL = 5;
const NS = D.stations.length, NE = D.edges.length, NK = D.satPrn.length, NEP = D.nEp;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const sysColor = s => `var(--s${s})`;
const t0 = Date.parse(D.t0);
const epTime = k => new Date(t0 + k * D.stepMin * 60000);
const fmtUTC = d => d.toISOString().slice(0, 16).replace("T", " ");
const fmtLocal = d => d.toLocaleString("hu-HU", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });

// --- állomások helyi bázisa (ugyanaz, mint a Pythonban) ---------------------
const ST = D.stations.map(([name, lat, lon, h]) => {
  const a = 6378137, f = 1 / 298.257223563, e2 = f * (2 - f);
  const la = lat * Math.PI / 180, lo = lon * Math.PI / 180;
  const N = a / Math.sqrt(1 - e2 * Math.sin(la) ** 2);
  const sl = Math.sin(la), cl = Math.cos(la), so = Math.sin(lo), co = Math.cos(lo);
  return { name, lat, lon,
    X: [(N + h) * cl * co, (N + h) * cl * so, (N * (1 - e2) + h) * sl],
    E: [-so, co, 0], Nn: [-sl * co, -sl * so, cl], U: [cl * co, cl * so, sl] };
});
const NB = Array.from({ length: NS }, () => []);
D.edges.forEach(([i, j], e) => { NB[i].push([j, e]); NB[j].push([i, e]); });

// műholdak bitpozíciója rendszerenként (két 32 bites szó / rendszer)
const satBit = new Int32Array(NK), perSys = [0, 0, 0, 0, 0];
for (let k = 0; k < NK; k++) satBit[k] = perSys[D.satSys[k]]++;

function azel(st, ep, k) {
  const o = (ep * NK + k) * 3;
  const dx = TRACK[o] - st.X[0], dy = TRACK[o + 1] - st.X[1], dz = TRACK[o + 2] - st.X[2];
  const e = dx * st.E[0] + dy * st.E[1];
  const n = dx * st.Nn[0] + dy * st.Nn[1] + dz * st.Nn[2];
  const u = dx * st.U[0] + dy * st.U[1] + dz * st.U[2];
  const r = Math.hypot(dx, dy, dz);
  return [((Math.atan2(e, n) * 180 / Math.PI) + 360) % 360, Math.asin(u / r) * 180 / Math.PI];
}

// --- teljes számítás: COUNTS[(ep*NE+e)*6+s] ----------------------------------
let COUNTS = null;
const popc = x => { x -= (x >>> 1) & 0x55555555; x = (x & 0x33333333) + ((x >>> 2) & 0x33333333); return (((x + (x >>> 4)) & 0x0F0F0F0F) * 0x01010101) >>> 24; };
function computeAll(maskDeg) {
  const sm = Math.sin(maskDeg * Math.PI / 180);
  const counts = new Uint8Array(NEP * NE * 6);
  const bits = new Uint32Array(NS * 10);
  for (let ep = 0; ep < NEP; ep++) {
    bits.fill(0);
    const base = ep * NK * 3;
    for (let i = 0; i < NS; i++) {
      const st = ST[i], X = st.X, U = st.U;
      for (let k = 0; k < NK; k++) {
        const o = base + k * 3;
        const dx = TRACK[o] - X[0], dy = TRACK[o + 1] - X[1], dz = TRACK[o + 2] - X[2];
        const u = dx * U[0] + dy * U[1] + dz * U[2];
        if (u >= Math.sqrt(dx * dx + dy * dy + dz * dz) * sm) {
          const b = satBit[k], w = i * 10 + D.satSys[k] * 2 + (b >> 5);
          bits[w] |= (1 << (b & 31));
        }
      }
    }
    for (let e = 0; e < NE; e++) {
      const a = D.edges[e][0] * 10, b = D.edges[e][1] * 10, o = (ep * NE + e) * 6;
      let tot = 0;
      for (let s = 0; s < 5; s++) {
        const c = popc(bits[a + 2 * s] & bits[b + 2 * s]) + popc(bits[a + 2 * s + 1] & bits[b + 2 * s + 1]);
        counts[o + s] = c; tot += c;
      }
      counts[o + 5] = tot;
    }
  }
  return counts;
}

// --- állapot ---------------------------------------------------------------
const state = { sys: ALL, ep: 0, mask: D.mask, thr: { single: D.threshold, all: D.threshold * 2 }, sel: null, playing: false };
const thrNow = () => state.sys === ALL ? state.thr.all : state.thr.single;
const sysName = s => s === ALL ? "Összes rendszer" : SYS[s].name;

// --- diverging szín a küszöbhöz képest --------------------------------------
function divColor(v, thr) {
  const d = v - thr;
  if (d <= -3) return "var(--d-3)"; if (d === -2) return "var(--d-2)"; if (d === -1) return "var(--d-1)";
  if (d === 0) return "var(--d0)"; if (d <= 2) return "var(--d1)"; if (d <= 5) return "var(--d2)"; return "var(--d3)";
}

// --- UI felépítése -----------------------------------------------------------
const $ = id => document.getElementById(id);
const NSVG = "http://www.w3.org/2000/svg";
const el = (tag, attrs = {}, parent) => { const n = document.createElementNS(NSVG, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); if (parent) parent.appendChild(n); return n; };

(function meta() {
  const t1 = epTime(NEP - 1);
  const ds = D.edges.map(e => e[2]);
  const elab = D.edgeKm ? `élhossz ${D.edgeKm} km` : `élhossz ${Math.min(...ds).toFixed(1)}–${Math.max(...ds).toFixed(1)} km`;
  $("meta").textContent = `${NS} állomás · ${NE} szomszédos pár · ${elab} · ` +
    `${fmtUTC(epTime(0))} – ${fmtUTC(t1)} UTC · ${D.stepMin} perces lépés · ${NK} műhold`;
  $("foot").textContent = "Számítás almanach alapján (km-es pontosság, láthatósághoz elegendő). " +
    (D.dropped.length ? `Elavult vagy hibás almanach miatt kihagyva: ${D.dropped.join(", ")}. ` : "") +
    "Közös műhold: mindkét állomásról a maszk fölött látszik. Domborzati takarás nincs figyelembe véve.";
})();

const seg = $("sysSeg");
[[ALL, "Összes", null], ...SYS.map((s, i) => [i, s.name, i])].forEach(([v, label, ci]) => {
  if (v !== ALL && !D.satSys.includes(v)) return;
  const b = document.createElement("button");
  b.type = "button"; b.dataset.v = v;
  b.innerHTML = (ci !== null ? `<span class="dot" style="background:${sysColor(ci)}"></span>` : "") + label;
  b.onclick = () => { state.sys = v; $("thr").value = thrNow(); renderAll(); };
  seg.appendChild(b);
});
$("mask").value = state.mask; $("maskV").textContent = state.mask + "°";
$("thr").value = thrNow();
$("time").max = NEP - 1;

// --- térkép -----------------------------------------------------------------
const map = $("map");
const lat0 = D.stations.reduce((a, s) => a + s[1], 0) / NS;
const kx = Math.cos(lat0 * Math.PI / 180);
let MB;
(function buildMap() {
  const pts = D.stations.map(s => [s[2], s[1]]);
  const all = pts.concat(D.outline ? D.outline.flat() : []);
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  all.forEach(([lo, la]) => { x0 = Math.min(x0, lo * kx); x1 = Math.max(x1, lo * kx); y0 = Math.min(y0, -la); y1 = Math.max(y1, -la); });
  const pad = (x1 - x0) * 0.03;
  MB = { x0: x0 - pad, y0: y0 - pad, w: x1 - x0 + 2 * pad, h: y1 - y0 + 2 * pad };
  const W = 1000, H = Math.round(W * MB.h / MB.w);
  map.setAttribute("viewBox", `0 0 ${W} ${H}`);
  MB.W = W; MB.H = H;
})();
const P = (lon, lat) => [((lon * kx - MB.x0) / MB.w) * MB.W, ((-lat - MB.y0) / MB.h) * MB.H];
if (D.outline) {
  const d = D.outline.map(r => "M" + r.map(([lo, la]) => P(lo, la).map(v => v.toFixed(1)).join(",")).join("L") + "Z").join("");
  el("path", { d, fill: "var(--land)", stroke: "var(--land-line)", "stroke-width": 1.2, "stroke-linejoin": "round" }, map);
}
const gEdges = el("g", { "stroke-linecap": "round" }, map);
const gHit = el("g", {}, map);
const gSt = el("g", {}, map);
const SP = D.stations.map(s => P(s[2], s[1]));
const scaleKm = MB.W / (MB.w * 111.32);
const medKm = (() => { const a = D.edges.map(e => e[2]).sort((x, y) => x - y); return a[a.length >> 1]; })();
const edgeW = Math.max(1.5, Math.min(4, (D.edgeKm || medKm) * scaleKm * 0.12));
const edgeEls = D.edges.map(([i, j]) => el("line", { x1: SP[i][0], y1: SP[i][1], x2: SP[j][0], y2: SP[j][1], "stroke-width": edgeW }, gEdges));
D.edges.forEach(([i, j], e) => {
  const h = el("line", { x1: SP[i][0], y1: SP[i][1], x2: SP[j][0], y2: SP[j][1], stroke: "transparent", "stroke-width": Math.max(10, edgeW * 3) }, gHit);
  h.addEventListener("pointermove", ev => showTip(ev, edgeTip(e)));
  h.addEventListener("pointerleave", hideTip);
});
const stR = Math.max(2.5, Math.min(6, edgeW * 1.4));
const stEls = D.stations.map((s, i) => {
  const c = el("circle", { cx: SP[i][0], cy: SP[i][1], r: stR, fill: "var(--ink)", stroke: "var(--surface)", "stroke-width": 1.5, style: "cursor:pointer" }, gSt);
  c.addEventListener("click", () => { state.sel = state.sel === i ? null : i; renderAll(); });
  c.addEventListener("pointermove", ev => showTip(ev, stTip(i)));
  c.addEventListener("pointerleave", hideTip);
  return c;
});
if (NS <= 60) D.stations.forEach((s, i) => {
  const t = el("text", { x: SP[i][0] + stR + 3, y: SP[i][1] - stR - 1, style: "font-size:12px;fill:var(--ink-2);pointer-events:none;paint-order:stroke;stroke:var(--surface);stroke-width:3px" }, gSt);
  t.textContent = s[0];
});
const selRing = el("circle", { r: stR + 5, fill: "none", stroke: "var(--sel)", "stroke-width": 2.5, visibility: "hidden" }, map);

function renderMapLegend() {
  const t = thrNow();
  const items = [[t - 3, `≤ ${t - 3}`], [t - 2, `${t - 2}`], [t - 1, `${t - 1}`], [t, `${t} (küszöb)`], [t + 1, `${t + 1}–${t + 2}`], [t + 3, `${t + 3}–${t + 5}`], [t + 6, `≥ ${t + 6}`]].filter(([v]) => v >= 0);
  $("mapLegend").innerHTML = `<span>Közös műhold (${sysName(state.sys)}):</span>` +
    items.map(([v, l]) => `<span><span class="sw" style="background:${divColor(v, t)}"></span>${l}</span>`).join("");
}

// --- tooltip ---------------------------------------------------------------
const tip = $("tip");
function showTip(ev, html) {
  tip.innerHTML = html; tip.style.display = "block";
  const r = tip.getBoundingClientRect();
  let x = ev.clientX + 14, y = ev.clientY + 14;
  if (x + r.width > innerWidth - 8) x = ev.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = ev.clientY - r.height - 14;
  tip.style.left = Math.max(8, x) + "px"; tip.style.top = Math.max(8, y) + "px";
}
function hideTip() { tip.style.display = "none"; }

function visibleAt(i, ep) {
  const sm = Math.sin(state.mask * Math.PI / 180), out = [];
  for (let k = 0; k < NK; k++) { const [az, e] = azel(ST[i], ep, k); out.push({ k, az, el: e, vis: Math.sin(e * Math.PI / 180) >= sm }); }
  return out;
}
function edgeTip(e) {
  const [i, j, dkm] = D.edges[e], o = (state.ep * NE + e) * 6;
  const vi = visibleAt(i, state.ep), vj = visibleAt(j, state.ep);
  const common = vi.filter((v, k) => v.vis && vj[k].vis && (state.sys === ALL || D.satSys[k] === state.sys)).map(v => D.satPrn[v.k]);
  const rows = SYS.map((s, si) => D.satSys.includes(si) ? `<span class="dot" style="background:${sysColor(si)}"></span> ${s.name}: <b>${COUNTS[o + si]}</b>` : "").filter(Boolean).join("<br>");
  return `<b>${ST[i].name} – ${ST[j].name}</b> <span class="m">${dkm.toFixed(2)} km</span><br>` +
    `Közös összesen: <b>${COUNTS[o + 5]}</b><br>${rows}<br><span class="m">${common.join(" ")}</span>`;
}
function stTip(i) {
  const v = visibleAt(i, state.ep);
  const n = SYS.map((s, si) => v.filter(x => x.vis && D.satSys[x.k] === si).length);
  return `<b>${ST[i].name}</b> <span class="m">${ST[i].lat.toFixed(4)}°, ${ST[i].lon.toFixed(4)}°</span><br>` +
    `Látható (maszk fölött): <b>${n.reduce((a, b) => a + b, 0)}</b><br><span class="m">Kattints a részletekért</span>`;
}

// --- KPI-k ------------------------------------------------------------------
function renderKpis() {
  const s = state.sys, t = thrNow();
  let mn = 1e9, mnE = 0, sum = 0, low = 0;
  for (let e = 0; e < NE; e++) { const v = COUNTS[(state.ep * NE + e) * 6 + s]; sum += v; if (v < t) low++; if (v < mn) { mn = v; mnE = e; } }
  let pmin = 1e9, pmEp = 0, lowAll = 0;
  for (let ep = 0; ep < NEP; ep++) for (let e = 0; e < NE; e++) { const v = COUNTS[(ep * NE + e) * 6 + s]; if (v < t) lowAll++; if (v < pmin) { pmin = v; pmEp = ep; } }
  const pe = D.edges[mnE];
  $("kpis").innerHTML = [
    ["Legkevesebb közös most", mn, `${ST[pe[0]].name} – ${ST[pe[1]].name}`],
    ["Átlag most", (sum / NE).toFixed(1), `${NE} pár átlaga`],
    ["Küszöb alatt most", `${low}`, `${(100 * low / NE).toFixed(1)}% · küszöb ${t}`],
    ["Időszak minimuma", pmin, `${fmtUTC(epTime(pmEp))} UTC · ${(100 * lowAll / (NE * NEP)).toFixed(2)}% pár-epoch < ${t}`],
  ].map(([k, v, s2]) => `<div class="kpi"><div class="k">${k}</div><div class="v">${v}</div><div class="s" title="${s2}">${s2}</div></div>`).join("");
}

// --- égbolt-ábra + állomás panel --------------------------------------------
const sky = $("sky");
function renderSky() {
  sky.innerHTML = "";
  const R = 110, rr = e => R * (90 - Math.max(e, 0)) / 90;
  [0, 30, 60].forEach(e => el("circle", { r: rr(e), fill: "none", stroke: "var(--grid)", "stroke-width": 1 }, sky));
  el("circle", { r: rr(state.mask), fill: "none", stroke: "var(--axis)", "stroke-width": 1.2, "stroke-dasharray": "4 3" }, sky);
  el("line", { x1: -R, y1: 0, x2: R, y2: 0, stroke: "var(--grid)" }, sky);
  el("line", { x1: 0, y1: -R, x2: 0, y2: R, stroke: "var(--grid)" }, sky);
  [["É", 0, -R - 8], ["K", R + 9, 4], ["D", 0, R + 15], ["NY", -R - 12, 4]].forEach(([t, x, y]) => { const n = el("text", { x, y, "text-anchor": "middle" }, sky); n.textContent = t; });
  [30, 60].forEach(e => { const n = el("text", { x: 3, y: -rr(e) - 2 }, sky); n.textContent = e + "°"; });
  if (state.sel === null) {
    $("stTitle").textContent = "Állomás"; $("stSub").textContent = "Kattints egy állomásra a térképen.";
    $("stTable").innerHTML = ""; $("skyLegend").innerHTML = ""; return;
  }
  const i = state.sel, v = visibleAt(i, state.ep);
  $("stTitle").textContent = ST[i].name;
  $("stSub").textContent = `${ST[i].lat.toFixed(5)}°, ${ST[i].lon.toFixed(5)}° · ${fmtUTC(epTime(state.ep))} UTC`;
  v.filter(x => x.el > 0).sort((a, b) => (D.satSys[a.k] === state.sys) - (D.satSys[b.k] === state.sys)).forEach(x => {
    const s = D.satSys[x.k], dim = state.sys !== ALL && s !== state.sys;
    const a = x.az * Math.PI / 180, r = rr(x.el), px = r * Math.sin(a), py = -r * Math.cos(a);
    const g = el("g", { opacity: dim ? 0.25 : 1 }, sky);
    el("circle", { cx: px, cy: py, r: 5.5, fill: x.vis ? sysColor(s) : "var(--surface)", stroke: x.vis ? "var(--surface)" : sysColor(s), "stroke-width": x.vis ? 1.5 : 1.8 }, g);
    const t = el("text", { x: px + 7.5, y: py + 3.5, style: "font-size:9.5px;fill:var(--ink-2)" }, g); t.textContent = D.satPrn[x.k];
  });
  $("skyLegend").innerHTML = SYS.map((s, si) => D.satSys.includes(si) ? `<span><span class="dot" style="background:${sysColor(si)}"></span> ${s.name}</span>` : "").join("") +
    `<span class="hint">üres kör = maszk alatt</span>`;
  const vis = SYS.map((s, si) => v.filter(x => x.vis && D.satSys[x.k] === si).length);
  let html = `<tr><th>Szomszéd</th><th class="n">km</th><th class="n">Közös (${state.sys === ALL ? "össz." : SYS[state.sys].id})</th></tr>`;
  NB[i].forEach(([j, e]) => {
    const c = COUNTS[(state.ep * NE + e) * 6 + state.sys];
    html += `<tr><td>${ST[j].name}</td><td class="n">${D.edges[e][2].toFixed(1)}</td><td class="n"><span class="chip" style="box-shadow: inset 0 -3px 0 ${divColor(c, thrNow())}">${c}</span></td></tr>`;
  });
  html += `<tr><th colspan="2">Látható műholdak</th><th class="n">db</th></tr>` +
    SYS.map((s, si) => D.satSys.includes(si) ? `<tr><td colspan="2"><span class="dot" style="background:${sysColor(si)}"></span> ${s.name}</td><td class="n">${vis[si]}</td></tr>` : "").join("");
  $("stTable").innerHTML = html;
}

// --- idősor grafikonok ---------------------------------------------------------
const ts = $("ts"), low = $("low");
const M = { l: 34, r: 12, t: 8, b: 26 };
function chartGeom(svg, H) {
  const W = Math.max(320, svg.parentElement.clientWidth - 28);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  return { W, H, x: k => M.l + (W - M.l - M.r) * k / (NEP - 1), iw: W - M.l - M.r, ih: H - M.t - M.b };
}
function timeAxis(svg, g) {
  const days = Math.ceil(NEP * D.stepMin / 1440) + 1;
  const start = new Date(epTime(0)); start.setUTCHours(0, 0, 0, 0);
  for (let d = 0; d <= days; d++) {
    const tt = start.getTime() + d * 86400000, k = (tt - t0) / (D.stepMin * 60000);
    if (k < 0 || k > NEP - 1) continue;
    el("line", { x1: g.x(k), x2: g.x(k), y1: M.t, y2: g.H - M.b, stroke: "var(--grid)" }, svg);
    const lab = el("text", { x: g.x(k) + 3, y: g.H - 8 }, svg);
    lab.textContent = new Date(tt).toISOString().slice(5, 10).replace("-", ".") + ".";
  }
  el("line", { x1: M.l, x2: g.W - M.r, y1: g.H - M.b, y2: g.H - M.b, stroke: "var(--axis)" }, svg);
}
function niceMax(v) { const s = [5, 10, 15, 20, 30, 40, 50, 60, 80, 100]; return s.find(x => x >= v) || Math.ceil(v / 20) * 20; }
let SER = null;
function seriesFor(s) {
  const t = thrNow(), mn = new Float32Array(NEP), mx = new Float32Array(NEP), mean = new Float32Array(NEP), lw = new Float32Array(NEP), sel = state.sel !== null ? new Float32Array(NEP) : null;
  for (let ep = 0; ep < NEP; ep++) {
    let a = 1e9, b = -1, sm = 0, l = 0;
    for (let e = 0; e < NE; e++) { const v = COUNTS[(ep * NE + e) * 6 + s]; if (v < a) a = v; if (v > b) b = v; sm += v; if (v < t) l++; }
    mn[ep] = a; mx[ep] = b; mean[ep] = sm / NE; lw[ep] = 100 * l / NE;
    if (sel) { let m = 1e9; NB[state.sel].forEach(([, e]) => { const v = COUNTS[(ep * NE + e) * 6 + s]; if (v < m) m = v; }); sel[ep] = m; }
  }
  return { mn, mx, mean, lw, sel };
}
function renderCharts() {
  SER = seriesFor(state.sys);
  const s = state.sys, col = s === ALL ? "var(--ink-2)" : sysColor(s), t = thrNow();
  // fő grafikon
  ts.innerHTML = "";
  const g = chartGeom(ts, 240);
  const ymax = niceMax(Math.max(t + 1, ...SER.mx));
  const y = v => M.t + g.ih * (1 - v / ymax);
  const step = ymax <= 10 ? 2 : ymax <= 20 ? 5 : ymax <= 50 ? 10 : 20;
  for (let v = 0; v <= ymax; v += step) {
    el("line", { x1: M.l, x2: g.W - M.r, y1: y(v), y2: y(v), stroke: "var(--grid)" }, ts);
    const n = el("text", { x: M.l - 6, y: y(v) + 3.5, "text-anchor": "end" }, ts); n.textContent = v;
  }
  timeAxis(ts, g);
  let band = "M";
  for (let k = 0; k < NEP; k++) band += `${g.x(k).toFixed(1)},${y(SER.mx[k]).toFixed(1)}L`;
  for (let k = NEP - 1; k >= 0; k--) band += `${g.x(k).toFixed(1)},${y(SER.mn[k]).toFixed(1)}${k ? "L" : "Z"}`;
  el("path", { d: band, fill: col, "fill-opacity": 0.16, stroke: "none" }, ts);
  const line = (arr, attrs) => el("path", Object.assign({ d: "M" + Array.from(arr, (v, k) => `${g.x(k).toFixed(1)},${y(v).toFixed(1)}`).join("L"), fill: "none", "stroke-width": 2, "stroke-linejoin": "round" }, attrs), ts);
  line(SER.mn, { stroke: col, "stroke-width": 1, "stroke-opacity": 0.7 });
  line(SER.mean, { stroke: col });
  if (SER.sel) line(SER.sel, { stroke: "var(--sel)" });
  el("line", { x1: M.l, x2: g.W - M.r, y1: y(t), y2: y(t), stroke: "var(--crit)", "stroke-width": 1.2, "stroke-dasharray": "5 4" }, ts);
  const tl = el("text", { x: g.W - M.r - 4, y: y(t) - 4, "text-anchor": "end", style: "fill:var(--crit)" }, ts); tl.textContent = `küszöb ${t}`;
  const cur = el("line", { x1: g.x(state.ep), x2: g.x(state.ep), y1: M.t, y2: g.H - M.b, stroke: "var(--ink)", "stroke-width": 1.2 }, ts);
  const hov = el("line", { y1: M.t, y2: g.H - M.b, stroke: "var(--muted)", "stroke-width": 1, visibility: "hidden" }, ts);
  $("tsTitle").textContent = `Közös műholdak a szomszédos párok között – ${sysName(s)}`;
  $("tsLeg").innerHTML = `<span><span class="sw" style="background:${col};opacity:.25"></span>min–max tartomány</span>` +
    `<span><span class="sw" style="background:${col};height:2px"></span>átlag</span>` +
    (SER.sel ? `<span><span class="sw" style="background:var(--sel);height:2px"></span>${ST[state.sel].name} legrosszabb szomszédja</span>` : "") +
    `<span><span class="sw" style="background:var(--crit);height:2px"></span>küszöb</span>`;
  // küszöb alatti arány
  low.innerHTML = "";
  const g2 = chartGeom(low, 130);
  const lmax = Math.max(5, niceMax(Math.max(...SER.lw)));
  const y2 = v => M.t + g2.ih * (1 - v / lmax);
  [0, lmax / 2, lmax].forEach(v => { el("line", { x1: M.l, x2: g2.W - M.r, y1: y2(v), y2: y2(v), stroke: "var(--grid)" }, low); const n = el("text", { x: M.l - 6, y: y2(v) + 3.5, "text-anchor": "end" }, low); n.textContent = Math.round(v) + "%"; });
  timeAxis(low, g2);
  let area = `M${g2.x(0)},${y2(0)}`;
  for (let k = 0; k < NEP; k++) area += `L${g2.x(k).toFixed(1)},${y2(SER.lw[k]).toFixed(1)}`;
  area += `L${g2.x(NEP - 1)},${y2(0)}Z`;
  el("path", { d: area, fill: "var(--crit)", "fill-opacity": 0.22, stroke: "none" }, low);
  el("path", { d: "M" + Array.from(SER.lw, (v, k) => `${g2.x(k).toFixed(1)},${y2(v).toFixed(1)}`).join("L"), fill: "none", stroke: "var(--crit)", "stroke-width": 1.5 }, low);
  const cur2 = el("line", { x1: g2.x(state.ep), x2: g2.x(state.ep), y1: M.t, y2: g2.H - M.b, stroke: "var(--ink)", "stroke-width": 1.2 }, low);
  const hov2 = el("line", { y1: M.t, y2: g2.H - M.b, stroke: "var(--muted)", "stroke-width": 1, visibility: "hidden" }, low);
  const totLow = SER.lw.reduce((a, b) => a + b, 0) / NEP;
  $("lowSub").textContent = `A szomszédos párok hány százalékánál van a közös műholdak száma a küszöb (${t}) alatt – ${sysName(s)}. Időszak átlaga: ${totLow.toFixed(2)}%.`;
  // interakció
  [[ts, g, hov], [low, g2, hov2]].forEach(([svg, gg, hl]) => {
    const kAt = ev => { const r = svg.getBoundingClientRect(); const px = (ev.clientX - r.left) * gg.W / r.width; return Math.max(0, Math.min(NEP - 1, Math.round((px - M.l) / gg.iw * (NEP - 1)))); };
    svg.onpointermove = ev => {
      const k = kAt(ev); [hov, hov2].forEach(h => { h.setAttribute("x1", g.x(k) * (h === hov ? 1 : g2.W / g.W)); });
      hov.setAttribute("x1", g.x(k)); hov.setAttribute("x2", g.x(k)); hov2.setAttribute("x1", g2.x(k)); hov2.setAttribute("x2", g2.x(k));
      hov.setAttribute("visibility", "visible"); hov2.setAttribute("visibility", "visible");
      const d = epTime(k);
      showTip(ev, `<b>${fmtUTC(d)} UTC</b> <span class="m">(${fmtLocal(d)} helyi)</span><br>` +
        `min <b>${SER.mn[k]}</b> · átlag <b>${SER.mean[k].toFixed(1)}</b> · max <b>${SER.mx[k]}</b><br>` +
        (SER.sel ? `${ST[state.sel].name} legrosszabb: <b>${SER.sel[k]}</b><br>` : "") +
        `küszöb alatt: <b>${SER.lw[k].toFixed(1)}%</b> <span class="m">(${Math.round(SER.lw[k] * NE / 100)} pár)</span>`);
    };
    svg.onpointerleave = () => { hov.setAttribute("visibility", "hidden"); hov2.setAttribute("visibility", "hidden"); hideTip(); };
    svg.onclick = ev => setEp(kAt(ev));
  });
  renderCharts.cur = [[cur, g], [cur2, g2]];
}

// --- renderelés ----------------------------------------------------------------
function renderMap() {
  const s = state.sys, t = thrNow(), o0 = state.ep * NE * 6;
  for (let e = 0; e < NE; e++) {
    const v = COUNTS[o0 + e * 6 + s];
    edgeEls[e].setAttribute("stroke", divColor(v, t));
    const hl = state.sel !== null && (D.edges[e][0] === state.sel || D.edges[e][1] === state.sel);
    edgeEls[e].setAttribute("stroke-width", hl ? edgeW * 2 : edgeW);
  }
  if (state.sel !== null) { selRing.setAttribute("cx", SP[state.sel][0]); selRing.setAttribute("cy", SP[state.sel][1]); selRing.setAttribute("visibility", "visible"); }
  else selRing.setAttribute("visibility", "hidden");
}
function renderTime() {
  const d = epTime(state.ep);
  $("time").value = state.ep;
  $("tLabel").innerHTML = `${fmtUTC(d)} UTC <small>· helyi ${fmtLocal(d)}</small>`;
  renderMap(); renderKpis(); renderSky();
  if (renderCharts.cur) renderCharts.cur.forEach(([c, g]) => { c.setAttribute("x1", g.x(state.ep)); c.setAttribute("x2", g.x(state.ep)); });
}
function renderAll() {
  seg.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(+b.dataset.v === state.sys)));
  renderMapLegend(); renderCharts(); renderTime();
}
function setEp(k) { state.ep = Math.max(0, Math.min(NEP - 1, k)); renderTime(); }

$("time").oninput = e => setEp(+e.target.value);
$("mask").oninput = e => { $("maskV").textContent = e.target.value + "°"; };
$("mask").onchange = e => { $("maskV").textContent = e.target.value + "°"; state.mask = +e.target.value; recompute(); };
$("thr").onchange = e => { const v = Math.max(0, +e.target.value || 0); if (state.sys === ALL) state.thr.all = v; else state.thr.single = v; renderAll(); };
let timer = null;
$("play").onclick = () => {
  state.playing = !state.playing;
  $("play").textContent = state.playing ? "❚❚" : "▶";
  $("play").setAttribute("aria-label", state.playing ? "Megállítás" : "Lejátszás");
  clearInterval(timer);
  if (state.playing) timer = setInterval(() => setEp(state.ep >= NEP - 1 ? 0 : state.ep + 1), +$("speed").value);
};
$("speed").onchange = () => { if (state.playing) { $("play").click(); $("play").click(); } };
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  if (e.key === "ArrowRight") setEp(state.ep + 1); else if (e.key === "ArrowLeft") setEp(state.ep - 1);
  else if (e.key === " ") { e.preventDefault(); $("play").click(); }
});
let rz; addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(renderCharts, 150); });

function recompute() {
  $("busy").textContent = "számolás…";
  setTimeout(() => {
    const t = performance.now();
    COUNTS = computeAll(state.mask);
    $("busy").textContent = `${NE} pár × ${NEP} epoch · ${Math.round(performance.now() - t)} ms`;
    renderAll();
  }, 20);
}
recompute();
</script>
</body>
</html>
"""
