#!/usr/bin/env python3
"""Music logo family, built on the geometry measured from the source link logo.

    python generate.py                 write every SVG + PNG next to this file
    python generate.py --sheet a.png   only render a contact sheet (fast, for iterating)

Every mark is a set of centerlines ("strands"). Where two strands of different
colours cross, the one going under is split so it ends in square-cut ends, the
way the source logo does it. No masks: gaps are real, so transparent PNGs work.
"""
import math, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image

W, G, R = 52, 18, 44          # stroke, weave gap, corner radius: measured from the source
CUT = W / 2 + G               # how far an under-strand stops from the crossing centre
SIZE = 1024
GRAD = {"g": ("#F5D888", "#C9A13D"), "s": ("#DDDAD3", "#98948D")}  # sampled from the source
BG_STOPS = [(0, "#151822"), (.3, "#10131B"), (.6, "#0C0E15"), (.87, "#07090D"), (1, "#05060A")]
# shortcut: PNGs are rendered by this machine's Edge, point this at Chrome on another machine
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
HERE = os.path.dirname(os.path.abspath(__file__))


# ---- geometry: a path is a list of line ('L', p0, p1) and arc ('A', c, r, a0, sweep) segments
def seg_len(s):
    return math.dist(s[1], s[2]) if s[0] == "L" else abs(s[2] * s[4])

def seg_pt(s, t):
    if s[0] == "L":
        return (s[1][0] + (s[2][0] - s[1][0]) * t, s[1][1] + (s[2][1] - s[1][1]) * t)
    a = s[3] + s[4] * t
    return (s[1][0] + s[2] * math.cos(a), s[1][1] + s[2] * math.sin(a))

def seg_sub(s, t0, t1):
    if s[0] == "L":
        return ("L", seg_pt(s, t0), seg_pt(s, t1))
    return ("A", s[1], s[2], s[3] + s[4] * t0, s[4] * (t1 - t0))

def path_len(segs):
    return sum(seg_len(s) for s in segs)

def path_slice(segs, s0, s1):
    out, pos = [], 0.0
    for s in segs:
        L = seg_len(s)
        a, b = max(s0, pos), min(s1, pos + L)
        if b - a > 1e-6:
            out.append(seg_sub(s, (a - pos) / L, (b - pos) / L))
        pos += L
    return out

def sample(segs, ds=2.0):
    """Points and arc positions along a path, every ds pixels or closer."""
    pts, pos, ss = [], 0.0, []
    for s in segs:
        L = seg_len(s)
        n = max(1, int(math.ceil(L / ds)))
        for i in range(n):
            pts.append(seg_pt(s, i / n))
            ss.append(pos + L * i / n)
        pos += L
    pts.append(seg_pt(segs[-1], 1))
    ss.append(pos)
    return np.array(pts), np.array(ss)

def poly(pts, r=R, closed=False):
    """Polyline with rounded corners; r is one radius or a per-vertex list."""
    n = len(pts)
    rs = r if isinstance(r, (list, tuple)) else [r] * n
    corners = {}
    for i in range(n) if closed else range(1, n - 1):
        p, v, q = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
        a1, a2 = math.atan2(v[1] - p[1], v[0] - p[0]), math.atan2(q[1] - v[1], q[0] - v[0])
        turn = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        rr = rs[i]
        t = rr * math.tan(abs(turn) / 2)
        p1 = (v[0] - math.cos(a1) * t, v[1] - math.sin(a1) * t)
        p2 = (v[0] + math.cos(a2) * t, v[1] + math.sin(a2) * t)
        sign = 1 if turn > 0 else -1
        c = (p1[0] + sign * rr * -math.sin(a1), p1[1] + sign * rr * math.cos(a1))
        corners[i] = (p1, p2, ("A", c, rr, a1 - sign * math.pi / 2, turn))
    segs = []
    idx = range(n) if closed else range(n - 1)
    for i in idx:
        j = (i + 1) % n
        start = corners[i][1] if i in corners else pts[i]
        end = corners[j][0] if j in corners else pts[j]
        if math.dist(start, end) > 1e-6:
            segs.append(("L", start, end))
        if j in corners:
            segs.append(corners[j][2])
    return segs

class T:
    """Turtle for curves: heading in degrees, 0 = east, 90 = south; positive turn = clockwise."""
    def __init__(self, x, y, heading):
        self.x, self.y, self.a, self.segs = x, y, math.radians(heading), []
    def f(self, d):
        nx, ny = self.x + d * math.cos(self.a), self.y + d * math.sin(self.a)
        self.segs.append(("L", (self.x, self.y), (nx, ny)))
        self.x, self.y = nx, ny
        return self
    def a_(self, r, deg):
        sw, sign = math.radians(deg), 1 if deg > 0 else -1
        c = (self.x + r * math.cos(self.a + sign * math.pi / 2), self.y + r * math.sin(self.a + sign * math.pi / 2))
        a0 = self.a - sign * math.pi / 2
        self.segs.append(("A", c, r, a0, sw))
        self.a += sw
        self.x, self.y = c[0] + r * math.cos(a0 + sw), c[1] + r * math.sin(a0 + sw)
        return self

def diamond(cx, cy, h, r=R):
    return poly([(cx - h, cy), (cx, cy - h), (cx + h, cy), (cx, cy + h)], r, closed=True)

def ring(cx, cy, r, start=0, sweep=360):
    return [("A", (cx, cy), r, math.radians(start), math.radians(sweep))]

def rrect(x0, y0, x1, y1, r=R):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], r, closed=True)

def line(*pts, r=R):
    return poly(list(pts), r)

def rot(segs, deg):
    """Rotate a path around the origin."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    f = lambda p: (p[0] * c - p[1] * s, p[0] * s + p[1] * c)
    return [("L", f(x[1]), f(x[2])) if x[0] == "L" else ("A", f(x[1]), x[2], x[3] + math.radians(deg), x[4]) for x in segs]

def is_closed(segs):
    return math.dist(seg_pt(segs[0], 0), seg_pt(segs[-1], 1)) < 1e-6


# ---- weaving
def crossings(a, b):
    """Every point where two centerlines cross, as (pos on a, pos on b, angle in degrees)."""
    pa, sa = sample(a)
    pb, sb = sample(b)
    A0, A1, B0, B1 = pa[:-1, None], pa[1:, None], pb[None, :-1], pb[None, 1:]
    da, db = A1 - A0, B1 - B0
    den = da[..., 0] * db[..., 1] - da[..., 1] * db[..., 0]
    den = np.where(np.abs(den) < 1e-12, np.nan, den)
    d = B0 - A0
    t = (d[..., 0] * db[..., 1] - d[..., 1] * db[..., 0]) / den
    u = (d[..., 0] * da[..., 1] - d[..., 1] * da[..., 0]) / den
    out = []
    for i, j in zip(*np.nonzero((t >= 0) & (t < 1) & (u >= 0) & (u < 1))):
        ang = math.degrees(math.acos(min(1, abs(np.dot(da[i, 0], db[0, j])) / (np.linalg.norm(da[i, 0]) * np.linalg.norm(db[0, j])))))
        out.append((sa[i] + (sa[i + 1] - sa[i]) * t[i, j], sb[j] + (sb[j + 1] - sb[j]) * u[i, j], ang))
    return sorted(out)

def weave(strands, flip=False, name="", top=None):
    """Split under-strands at crossings; returns {colour: [path pieces]}. Over/under alternates."""
    cuts = [[] for _ in strands]
    for i, (a, ca) in enumerate(strands):
        for j, (b, cb) in enumerate(strands):
            if j <= i or ca == cb:
                continue
            for k, (sa, sb, ang) in enumerate(crossings(a, b)):
                # square-cut ends only sit parallel to the strand on top when the crossing is square
                assert ang > 80, f"{name}: crossing at {ang:.0f} degrees, redraw it closer to square"
                j_under = cb != top if top else (k + i + j + flip) % 2 == 0
                under, s = (j, sb) if j_under else (i, sa)
                cuts[under].append(s)
    out = {"g": [], "s": []}
    for (segs, col), cs in zip(strands, cuts):
        L = path_len(segs)
        if not cs:
            out[col].append(segs)
            continue
        cs = sorted(cs)
        if is_closed(segs):
            spans = [(cs[n] + CUT, cs[(n + 1) % len(cs)] - CUT + (L if n == len(cs) - 1 else 0)) for n in range(len(cs))]
        else:
            spans = [(0, cs[0] - CUT)] + [(cs[n] + CUT, cs[n + 1] - CUT) for n in range(len(cs) - 1)] + [(cs[-1] + CUT, L)]
        for s0, s1 in spans:
            if s1 <= 0.5 and not is_closed(segs):
                continue
            assert s1 - s0 > 20, f"{name}: leftover piece only {s1 - s0:.0f}px long"
            if s1 > L:  # piece wraps past the start of a closed loop
                out[col].append(path_slice(segs, s0, L) + path_slice(segs, 0, s1 - L))
            else:
                out[col].append(path_slice(segs, s0, s1))
    return out


# ---- output
def outline_pts(pieces):
    """Points on both edges of the stroke, for bounding box and gradient extents."""
    res = []
    for segs in pieces:
        p, _ = sample(segs, 1.0)
        t = np.gradient(p, axis=0)
        n = np.stack([-t[:, 1], t[:, 0]], 1) / np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
        res += [p + n * W / 2, p - n * W / 2]
    return np.vstack(res)

def shift(segs, dx, dy):
    out = []
    for s in segs:
        if s[0] == "L":
            out.append(("L", (s[1][0] + dx, s[1][1] + dy), (s[2][0] + dx, s[2][1] + dy)))
        else:
            out.append(("A", (s[1][0] + dx, s[1][1] + dy), s[2], s[3], s[4]))
    return out

def to_d(segs):
    d = "M%.2f %.2f" % seg_pt(segs[0], 0)
    for s in segs:
        if s[0] == "L":
            d += "L%.2f %.2f" % s[2]
        else:
            n = max(1, int(math.ceil(abs(s[4]) / math.radians(170))))  # SVG cannot draw a full circle in one arc
            for k in range(1, n + 1):
                d += "A%g %g 0 0 %d %.2f %.2f" % (s[2], s[2], s[4] > 0, *seg_pt(s, k / n))
    if is_closed(segs):
        d += "Z"
    return d

def build(mark):
    parts = weave(mark["strands"], mark.get("flip", False), mark["name"], mark.get("top"))
    pts = outline_pts(parts["g"] + parts["s"])
    nx, ny = mark.get("nudge", (0, 0))
    dx = SIZE / 2 - (pts[:, 0].min() + pts[:, 0].max()) / 2 + nx
    dy = SIZE / 2 - (pts[:, 1].min() + pts[:, 1].max()) / 2 + ny
    return {c: [shift(p, dx, dy) for p in ps] for c, ps in parts.items()}

def svg(parts, variant):
    defs, body = "", ""
    for c, pieces in parts.items():
        if not pieces:
            continue
        if variant == "gold":
            m = outline_pts(pieces).sum(axis=1)
            a, b = GRAD[c]
            defs += (f'<linearGradient id="{c}" gradientUnits="userSpaceOnUse" x1="{m.min()/2:.1f}" y1="{m.min()/2:.1f}" '
                     f'x2="{m.max()/2:.1f}" y2="{m.max()/2:.1f}"><stop stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>')
            stroke = f"url(#{c})"
        else:
            stroke = "#000" if variant == "black" else "#fff"
        body += f'<path stroke="{stroke}" d="{"".join(to_d(p) for p in pieces)}"/>'
    bg = ""
    if variant == "gold":
        stops = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in BG_STOPS)
        defs += f'<radialGradient id="bg" gradientUnits="userSpaceOnUse" cx="512" cy="470" r="800">{stops}</radialGradient>'
        bg = f'<rect width="{SIZE}" height="{SIZE}" fill="url(#bg)"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" viewBox="0 0 {SIZE} {SIZE}">'
            f'<defs>{defs}</defs>{bg}<g fill="none" stroke-width="{W}">{body}</g></svg>')

def shoot(src, png, w, h):
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([EDGE, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--default-background-color=00000000", f"--user-data-dir={prof}", f"--window-size={w + 100},{h + 200}",
                        f"--screenshot={png}", "file:///" + src.replace("\\", "/")],
                       check=True, capture_output=True, timeout=120)
    # headless Edge reserves part of the window for UI, so shoot oversize and crop
    Image.open(png).convert("RGBA").crop((0, 0, w, h)).save(png)

def sheet(out, cols=4, cell=360, variant="gold", marks=None):
    marks = marks if marks is not None else MARKS
    rows = math.ceil(len(marks) / cols)
    bg = {"gold": "#000", "black": "#fff", "white": "#111"}[variant]
    cells = ""
    for m in marks:
        s = svg(build(m), variant).replace(f'width="{SIZE}" height="{SIZE}" viewBox', f'width="{cell}" height="{cell}" viewBox')
        # ids must be unique once several SVGs share one page
        slug = m["name"].replace("-", "")
        s = s.replace('id="', f'id="{slug}').replace('url(#', f'url(#{slug}')
        cells += f'<div style="position:relative;width:{cell}px;height:{cell}px">{s}<span style="position:absolute;left:10px;top:8px;font:13px sans-serif;color:#888">{m["name"]}</span></div>'
    html = f'<!doctype html><body style="margin:0;background:{bg};display:grid;grid-template-columns:repeat({cols},{cell}px)">{cells}</body>'
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
    shoot(f.name, out, cols * cell, rows * cell)
    os.unlink(f.name)


# ---- the source logo, rebuilt: used only to prove the geometry matches
SOURCE = {"name": "source", "flip": True, "strands": [(diamond(-100, 0, 220), "g"), (diamond(100, 0, 220), "s")]}


def note_head(cx, cy, h):
    """Diamond notehead plus the x of its right apex, where a stem leaves tangentially."""
    return diamond(cx, cy, h), cx + h - R * (math.sqrt(2) - 1)

def chevron(apex, t, side=1):
    """A '>' (side=1) or '<' (side=-1) with its point at x=apex*side and arms t long in x and y."""
    return line((side * (apex - t), -t), (side * apex, 0), (side * (apex - t), t))

def dot(x, y):
    """A solid diamond: a butt-capped stroke exactly as long as it is wide, on the diagonal."""
    k = W / 2 / math.sqrt(2)
    return line((x - k, y - k), (x + k, y + k))

def clef():
    x, yb, xl, r1 = 30, 245, -175, 155
    crown = -230
    silver = T(x - 120, crown, -90).a_(60, 180).f(310 - crown).a_(50, 155)
    top = crown + G
    drop, lat = yb - r1 - top, (x - 120) - xl
    th = 2 * math.atan2(lat, drop)
    rs = drop / math.sin(th) / 2
    gold = T(x - 120, top, 90).a_(rs, math.degrees(th)).a_(rs, -math.degrees(th))
    gold.a_(r1, -90).f(100).a_(115, -90).a_(115, -90).f(100).a_(80, -90).a_(58, -70)
    return [(gold.segs, "g"), (silver.segs, "s")]

_h1, _x1 = note_head(-225, 190, 125)
_h2, _x2 = note_head(165, 190, 125)
_solo, _sx = note_head(-130, 190, 150)
_ln1 = diamond(-125, 165, 170)
_ln2, _lnx = note_head(40, 165, 170)
_lnt = -125, 165 - 170 + R * (math.sqrt(2) - 1)  # top apex of the gold link, where its stem leaves
ST = -14

MARKS = [
    {"name": "link-note", "strands": [
        (_ln1, "g"), (_ln2, "s"), (line((_lnx, 165), (_lnx, -320)), "s"),
        (line(_lnt, (_lnt[0], -294), (_lnx - CUT, -294)), "g")]},
    {"name": "duet", "strands": [
        (_h1, "g"), (line((_x1, 190), (_x1, -285), (_x2 + 26, -285)), "g"),
        (_h2, "s"), (line((_x2, 190), (_x2, -215), (_x1 + CUT, -215)), "s")]},
    {"name": "solo", "strands": [
        (_solo, "g"), (line((_sx, 190), (_sx, -340)), "g"),
        (line((_sx + CUT, -314), (_sx + 90, -314), (_sx + 270, -134), (_sx + 140, -4), r=[0, 70, 90, 0]), "s")]},
    {"name": "clef", "strands": clef()},
    {"name": "sharp", "strands": [
        (rot(line((-95, 295), (-95, -295), (95, -295), (95, 295), r=[0, 95, 95, 0]), ST), "g"),
        (rot(line((-295, -95), (295, -95), (295, 95), (-295, 95), r=[0, 95, 95, 0]), ST), "s")]},
    {"name": "encore", "strands": [
        (poly([(-300, -300), (0, 0), (-300, 300)], R, closed=True), "g"),
        (diamond(80, 0, 235), "s")]},
    {"name": "wave", "top": "s", "strands": [
        (line((-240, 100), (-240, -130), (-120, -130), (-120, 240), (0, 240), (0, -240), (120, -240), (120, 130), (240, 130), (240, -100),
              r=[0, 60, 60, 60, 60, 60, 60, 60, 60, 0]), "g"),
        (line((-196, 0), (-44, 0)), "s"), (line((44, 0), (196, 0)), "s")]},
    {"name": "equalizer", "top": "s", "strands": [
        (line((-240, -125), (-240, 125)), "g"), (line((-120, -205), (-120, 205)), "g"),
        (line((0, -310), (0, 310)), "g"), (line((120, -205), (120, 205)), "g"), (line((240, -125), (240, 125)), "g"),
        (line((-196, 0), (-44, 0)), "s"), (line((44, 0), (196, 0)), "s")]},
    {"name": "headphones", "top": "g", "strands": [
        (T(-205, 160, -90).f(200).a_(205, 180).f(200).segs, "g"),
        (rrect(-305, 50, -105, 290, 56), "s"), (rrect(105, 50, 305, 290, 56), "s")]},
    {"name": "mic", "strands": [
        (rrect(-95, -330, 95, 40, 95), "g"), (line((0, 40), (0, 300)), "g"), (line((-130, 300), (130, 300)), "g"),
        (line((-175, -130), (-175, 140), (175, 140), (175, -130), r=[0, 110, 110, 0]), "s")]},
    {"name": "vinyl", "strands": [
        (ring(0, 0, 280), "g"), (ring(0, 0, 178, -5, 280), "g"),
        (ring(0, 0, 75), "s"), (line((84, -84), (262, -262), (262, -360), r=[0, 44, 0]), "s")]},
    {"name": "broadcast", "strands": [
        (diamond(0, 0, 112), "g"),
        (chevron(218, 150), "s"), (chevron(218, 150, -1), "s"),
        (chevron(324, 190), "g"), (chevron(324, 190, -1), "g")]},
    {"name": "cassette", "strands": [
        (rrect(-315, -205, 315, 205, 60), "g"),
        (line((-205, 205), (-105, 105), (105, 105), (205, 205), r=[0, 36, 36, 0]), "g"),
        (ring(-140, -60, 62), "s"), (ring(140, -60, 62), "s"), (line((-78, -60), (78, -60)), "s")]},
    {"name": "bass", "strands": [
        (diamond(-170, 10, 85), "g"),
        (T(-170 - 85 + R * (math.sqrt(2) - 1), 10, -90).a_(237, 180).a_(340, 70).segs, "g"),
        (dot(338, -85), "s"), (dot(338, 85), "s")]},
]


def check_png(path, variant):
    """Fail loudly if a rendered file is not what the variant promises."""
    im = Image.open(path)
    assert im.size == (SIZE, SIZE), f"{path}: wrong size {im.size}"
    if variant == "gold":
        assert im.mode == "RGB", f"{path}: gold variant should be opaque"
        ink = np.abs(np.array(im, dtype=int) - np.array(im)[0, 0]).sum(axis=2) > 120
    else:
        a = np.array(im)
        assert (a[[0, 0, -1, -1], [0, -1, 0, -1], 3] == 0).all(), f"{path}: background is not transparent"
        want = 0 if variant == "black" else 255
        assert (a[a[..., 3] == 255][:, :3] == want).all(), f"{path}: stray colour in {variant} variant"
        ink = a[..., 3] > 128
    ys, xs = np.nonzero(ink)
    assert min(xs.min(), ys.min(), SIZE - 1 - xs.max(), SIZE - 1 - ys.max()) >= 150, f"{path}: mark too close to the edge"
    assert abs(xs.min() + xs.max() - SIZE + 1) <= 4 and abs(ys.min() + ys.max() - SIZE + 1) <= 4, f"{path}: mark off centre"

def export():
    for n, m in enumerate(MARKS, 1):
        folder = os.path.join(HERE, f"{n:02d}-{m['name']}")
        os.makedirs(folder, exist_ok=True)
        parts = build(m)
        for variant in ("gold", "black", "white"):
            base = os.path.join(folder, f"{m['name']}-{variant}")
            with open(base + ".svg", "w", encoding="utf-8") as f:
                f.write(svg(parts, variant))
            shoot(base + ".svg", base + ".png", SIZE, SIZE)
            if variant == "gold":  # same as the source: dark variant is an opaque app-icon square
                Image.open(base + ".png").convert("RGB").save(base + ".png")
            check_png(base + ".png", variant)
        print("ok", m["name"])
    sheet(os.path.join(HERE, "preview.png"), cols=5, marks=[SOURCE] + MARKS)


if __name__ == "__main__":
    if "--sheet" in sys.argv:
        sheet(os.path.abspath(sys.argv[sys.argv.index("--sheet") + 1]), cols=5, marks=[SOURCE] + MARKS)
    else:
        export()
