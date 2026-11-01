#!/usr/bin/env python3
"""Build the puzzle data embedded in ../../index.html.

Source of the silhouettes: the **KiloGram** dataset
(https://github.com/lil-lab/kilogram), whose SVG files encode the 7 tangram
pieces (polygons with ids 1..7) for each of ~1000 figures digitised from
J. Slocum, *The Tangram Book* (2003).  The SVGs are only available for
educational / research use; see tools/README.md for the full notice.

Pipeline
--------
1. Download the chosen figures' SVGs into ``kg_svg/`` (cached).
2. For each SVG, recover the piece polygons, the scale ``u`` and match every
   polygon against the canonical tangram piece it represents.
3. Re-express everything in *canonical* units (small triangle leg = 1) with the
   silhouette's bounding box moved to the origin.
4. The three classic levels (Square / Triangle / Rectangle) are solved from
   scratch here with ``solve.py``.
5. Write ``puzzles.json`` and, with ``--inject``, rewrite the
   ``<script id="puzzles-data">`` block inside ``../../index.html``.

Run from this directory:

    python3 build_puzzles.py            # writes puzzles.json
    python3 build_puzzles.py --inject   # also updates ../../index.html
"""
import argparse
import json
import math
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SVG_DIR = os.path.join(HERE, "kg_svg")
RAW = "https://raw.githubusercontent.com/lil-lab/kilogram/main/dataset/tangrams-svg/"

# figure slug -> KiloGram svg id (page<sheet>-<index>)
IDS = {
    "swan": "page8-18", "fish": "page7-73", "cat": "page5-96", "dog": "page8-234",
    "bird": "page8-22", "duck": "page8-129", "turtle": "page5-68", "crab": "page5-153",
    "horse": "page5-84", "fox": "page5-85", "giraffe": "page4-244", "dinosaur": "page6-128",
    "whale": "page8-65", "goose": "page8-236", "butterfly": "page4-180", "elephant": "page7-242",
    "penguin": "page7-112", "squirrel": "page5-94", "camel": "page8-21", "snail": "page5-240",
    "boat": "page8-204", "house": "page1-133", "rocket": "page6-107", "candle": "page4-98",
    "flower": "page5-211", "snake": "page8-182", "bat": "page7-85",
    # extra classic figures
    "rabbit": "page3-201", "owl": "page6-31", "frog": "page7-209", "pig": "page1-13",
    "bear": "page8-85", "lion": "page7-220", "seal": "page7-34", "flamingo": "page8-11",
    "ostrich": "page5-6", "hen": "page4-92", "dragon": "page7-67", "cobra": "page5-95",
    "robot": "page2-16", "bridge": "page7-87", "lamp": "page2-190", "sword": "page9-38",
    "axe": "page8-211", "ship": "page3-131", "mountain": "page7-15", "pinwheel": "page5-123",
}
# display order (easy / recognisable first)
ORDER = ["house", "boat", "rocket", "candle", "flower", "bridge", "mountain", "pinwheel",
         "lamp", "robot", "sword", "axe", "ship",
         "cat", "dog", "fox", "horse", "rabbit", "squirrel", "pig",
         "bird", "duck", "goose", "swan", "penguin", "bat", "butterfly", "owl", "hen",
         "fish", "whale", "turtle", "crab", "snail", "snake", "cobra", "frog",
         "camel", "elephant", "giraffe", "dinosaur", "lion", "bear", "seal",
         "flamingo", "ostrich", "dragon"]
NAMES = {k: k.title() for k in IDS}

# canonical pieces: small-triangle leg = 1
CAN = {
    "S": [(0, 0), (1, 0), (0, 1)],
    "M": [(0, 0), (2, 0), (1, 1)],
    "L": [(0, 0), (2, 0), (0, 2)],
    "Q": [(0, 0), (1, 0), (1, 1), (0, 1)],
    "P": [(0, 0), (1, 0), (2, 1), (1, 1)],
}
AREA = {"S": 0.5, "M": 1.0, "L": 2.0, "Q": 1.0, "P": 1.0}


# --------------------------------------------------------------------------- #
# small geometry helpers
# --------------------------------------------------------------------------- #
def rot(p, deg):
    r = math.radians(deg)
    c = round(math.cos(r), 9)
    s = round(math.sin(r), 9)
    return [(x * c - y * s, x * s + y * c) for x, y in p]


def norm(p):
    mnx = min(q[0] for q in p)
    mny = min(q[1] for q in p)
    return [(q[0] - mnx, q[1] - mny) for q in p]


def poly_area(p):
    a = 0
    for i in range(len(p)):
        x1, y1 = p[i]
        x2, y2 = p[(i + 1) % len(p)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def align_err(a, b):
    """Worst vertex distance under the best nearest-neighbour bijection."""
    if len(a) != len(b):
        return 1e9
    used = [False] * len(b)
    worst = 0.0
    for v in a:
        best, bi = 1e9, -1
        for j, w in enumerate(b):
            if used[j]:
                continue
            d = math.hypot(v[0] - w[0], v[1] - w[1])
            if d < best:
                best, bi = d, j
        if bi < 0:
            return 1e9
        used[bi] = True
        worst = max(worst, best)
    return worst


def match_piece(poly):
    """Return (error, (type, rotation_index, mirrored)) for a polygon."""
    target = norm(poly)
    area = poly_area(poly)
    best = (1e9, None)
    for typ, base in CAN.items():
        if abs(area - AREA[typ]) > 0.2:
            continue
        mirrors = (False, True) if typ == "P" else (False,)
        for m in mirrors:
            b = [(x, -y) for x, y in base] if m else base
            for k in range(8):
                e = align_err(target, norm(rot(b, 45 * k)))
                if e < best[0]:
                    best = (e, (typ, k, m))
    return best


# --------------------------------------------------------------------------- #
# download + extraction
# --------------------------------------------------------------------------- #
def download():
    os.makedirs(SVG_DIR, exist_ok=True)
    for slug, fig in IDS.items():
        dest = os.path.join(SVG_DIR, fig + ".svg")
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            continue
        print("download", fig)
        with urllib.request.urlopen(RAW + fig + ".svg", timeout=30) as r:
            open(dest, "wb").write(r.read())


def parse(path):
    s = open(path).read()
    polys = {}
    for m in re.finditer(r'<polygon[^>]*id="(\d+)"[^>]*points="([^"]+)"', s):
        polys[m.group(1)] = [tuple(map(float, xy.split(","))) for xy in m.group(2).split()]
    return polys


def assemble(polys):
    """polys: {id: [(x,y)...]} raw svg -> canonical pieces, or None."""
    if len(polys) != 7:
        return None
    area = sum(poly_area(p) for p in polys.values())
    u = math.sqrt(area / 8.0)
    pieces = []
    for pts in polys.values():
        cp = [(x / u, y / u) for x, y in pts]
        err, info = match_piece(cp)
        if info is None or err > 0.06:
            return None
        typ, k, m = info
        pieces.append({"type": typ, "poly": cp, "k": k, "m": bool(m)})
    xs = [q[0] for p in pieces for q in p["poly"]]
    ys = [q[1] for p in pieces for q in p["poly"]]
    mnx, mny = min(xs), min(ys)
    for p in pieces:
        p["poly"] = [[round(x - mnx, 6), round(y - mny, 6)] for x, y in p["poly"]]
    types = "".join(sorted(p["type"] for p in pieces))
    if types != "LLMPQSS":
        return None
    return pieces


def classic():
    sys.path.insert(0, HERE)
    import solve as S
    s2 = 2 * math.sqrt(2)
    out = []
    shapes = [("Square", [(0, 0), (8, 0), (8, 8), (0, 8)]),
              ("Triangle", [(0, 0), (16, 0), (8, 8)]),
              ("Rectangle", [(0, 0), (8, 8), (4, 12), (-4, 4)])]
    for name, outline in shapes:
        res = S.solve(outline)
        if not res.get("ok"):
            raise SystemExit("classic solve failed: " + name)
        polys = {str(i): [(x / s2, y / s2) for x, y in p["poly"]]
                 for i, p in enumerate(res["pieces"])}
        pieces = assemble(polys)
        if pieces is None:
            raise SystemExit("classic assemble failed: " + name)
        out.append({"name": name, "pieces": pieces})
    return out


# --------------------------------------------------------------------------- #
# inject into index.html
# --------------------------------------------------------------------------- #
def inject(puzzles_path):
    html_path = os.path.join(ROOT, "index.html")
    html = open(html_path).read()
    payload = json.dumps(json.load(open(puzzles_path)), separators=(",", ":"))
    pat = re.compile(r'(<script id="puzzles-data" type="application/json">).*?(</script>)', re.S)
    if not pat.search(html):
        # first run: the placeholder is present
        html = html.replace("__PUZZLES__", payload)
    else:
        html = pat.sub(lambda m: m.group(1) + payload + m.group(2), html)
    open(html_path, "w").write(html)
    print("injected", len(payload), "bytes into", html_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", action="store_true", help="also rewrite index.html")
    ap.add_argument("--no-download", action="store_true", help="use cached SVGs only")
    args = ap.parse_args()

    if not args.no_download:
        download()

    puzzles = classic()
    for slug in ORDER:
        fig = IDS[slug]
        path = os.path.join(SVG_DIR, fig + ".svg")
        pieces = assemble(parse(path))
        if pieces is None:
            print("skip", slug)
            continue
        puzzles.append({"name": NAMES[slug], "pieces": pieces})
        print("%-10s %s" % (slug, "".join(sorted(p["type"] for p in pieces))))

    out = os.path.join(HERE, "puzzles.json")
    json.dump(puzzles, open(out, "w"), separators=(",", ":"))
    print("wrote", out, "with", len(puzzles), "puzzles")
    if args.inject:
        inject(out)


if __name__ == "__main__":
    main()
