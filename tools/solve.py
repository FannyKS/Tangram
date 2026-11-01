#!/usr/bin/env python3
"""Tangram tiling solver (authoring tool).

All piece vertices are integer points on the lattice and every edge runs along
x=c, y=c, x+y=c or x-y=c. Such shapes are unions of quarter-cell triangles, so
we rasterise the target and each piece orientation onto that triangle grid and
run an exact-cover DFS.
"""
import json
import sys

sys.setrecursionlimit(10000)

BASE = {
    "L": [(0, 0), (8, 0), (4, 4)],   # large  triangle, area 16
    "M": [(0, 0), (4, 0), (4, 4)],   # medium triangle, area 8
    "S": [(0, 0), (4, 0), (2, 2)],   # small  triangle, area 4
    "Q": [(0, 0), (2, 2), (4, 0), (2, -2)],  # square, area 8
    "P": [(0, 0), (4, 0), (6, 2), (2, 2)],   # parallelogram, area 8
}
AVAIL = {"L": 2, "M": 1, "S": 2, "Q": 1, "P": 1}
ORDER = ["L", "M", "S", "Q", "P"]


def rot90(p):
    return [(-y, x) for (x, y) in p]


def mirror(p):
    return [(x, -y) for (x, y) in p]


def norm(p):
    mx = min(x for x, y in p)
    my = min(y for x, y in p)
    return [(x - mx, y - my) for x, y in p]


def vkey(p):
    return ";".join(sorted(f"{x},{y}" for x, y in p))


def orientations(t):
    variants = [BASE[t]]
    if t == "P":
        variants.append(mirror(BASE[t]))
    out, seen = [], set()
    for v in variants:
        p = v
        for _ in range(4):
            n = norm(p)
            k = vkey(n)
            if k not in seen:
                seen.add(k)
                out.append(p)
            p = rot90(p)
    return out


def point_in_poly(px, py, poly):
    inside = False
    n = len(poly)
    for a in range(n):
        ax, ay = poly[a]
        bx, by = poly[(a - 1) % n]
        if (ay > py) != (by > py):
            if px < (bx - ax) * (py - ay) / (by - ay) + ax:
                inside = not inside
    return inside


def raster(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    ox, oy = minx, miny
    tris = []
    for i in range(minx, maxx):
        for j in range(miny, maxy):
            c = (i + 0.5, j + 0.5)
            defs = {
                "N": (c, (i, j + 1), (i + 1, j + 1)),
                "E": (c, (i + 1, j), (i + 1, j + 1)),
                "S": (c, (i, j), (i + 1, j)),
                "W": (c, (i, j), (i, j + 1)),
            }
            for t, vs in defs.items():
                cx = (vs[0][0] + vs[1][0] + vs[2][0]) / 3
                cy = (vs[0][1] + vs[1][1] + vs[2][1]) / 3
                if point_in_poly(cx, cy, poly):
                    tris.append((i - ox, j - oy, t))
    return tris


def area(poly):
    s = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


PIECES = {t: [ (raster(norm(p)), norm(p)) for p in orientations(t)] for t in BASE}


def solve(poly, max_nodes=8_000_000):
    tris = raster(poly)
    target = set(f"{i},{j},{t}" for i, j, t in tris)
    want = round(area(poly) * 4)
    if len(target) != want:
        return {"error": f"raster {len(target)} != {want}"}

    def orderkey(tid):
        i, j, t = tid.split(",")
        return (int(j), int(i), t)

    order = sorted(target, key=orderkey)
    used = set()
    counts = {t: 0 for t in BASE}
    strip = []
    state = {"nodes": 0, "stop": False}

    def first_open():
        for tid in order:
            if tid not in used:
                return tid
        return None

    def dfs(remaining):
        if remaining == 0:
            return first_open() is None
        state["nodes"] += 1
        if state["nodes"] > max_nodes:
            state["stop"] = True
            raise RuntimeError("node cap")
        t0 = first_open()
        if t0 is None:
            return remaining == 0
        i0, j0, ty0 = t0.split(",")
        i0, j0 = int(i0), int(j0)
        for typ in ORDER:
            if counts[typ] >= AVAIL[typ]:
                continue
            for raster_tris, poly in PIECES[typ]:
                for di, dj, dt in raster_tris:
                    if dt != ty0:
                        continue
                    ox, oy = i0 - di, j0 - dj
                    placed = []
                    ok = True
                    for pi, pj, pt in raster_tris:
                        tid = f"{pi + ox},{pj + oy},{pt}"
                        if tid not in target or tid in used:
                            ok = False
                            break
                        placed.append(tid)
                    if not ok:
                        continue
                    for tid in placed:
                        used.add(tid)
                    counts[typ] += 1
                    strip.append((typ, poly, ox, oy))
                    if dfs(remaining - 1):
                        return True
                    strip.pop()
                    counts[typ] -= 1
                    for tid in placed:
                        used.remove(tid)
        return False

    try:
        ok = dfs(7)
    except RuntimeError:
        return {"ok": False, "nodes": state["nodes"], "error": "node cap"}
    # strip entries -> actual placed polygon (normed piece poly shifted by offset)
    out = []
    for typ, poly, ox, oy in strip:
        out.append({"type": typ, "poly": [[x + ox, y + oy] for x, y in poly]})
    return {"ok": ok, "strip": strip, "nodes": state["nodes"], "want": want, "pieces": out}


def tris_to_polygon(cells):
    """Convert a set of quarter-cell triangles back into an outline polygon.

    Uses the shared small-triangle lattice; builds edges and walks them.
    """
    edges = {}
    for (i, j), ts in cells.items():
        for t in ts:
            c = (i + 0.5, j + 0.5)
            corners = {
                "N": ((i, j + 1), (i + 1, j + 1)),
                "E": ((i + 1, j), (i + 1, j + 1)),
                "S": ((i, j), (i + 1, j)),
                "W": ((i, j), (i, j + 1)),
            }[t]
            a, b, d = c, corners[0], corners[1]
            for u, v in ((a, b), (b, d), (d, a)):
                e = (u, v)
                r = (v, u)
                if r in edges:
                    edges.pop(r)
                else:
                    edges[e] = True
    # merge collinear edges then walk
    pts = {}
    for (u, v) in edges:
        pts.setdefault(u, []).append(v)
    # start from lowest-left point
    start = min(pts, key=lambda p: (p[1], p[0]))
    poly = [start]
    cur = start
    prev = None
    for _ in range(10000):
        nxts = [v for v in pts.get(cur, []) if v != prev]
        if not nxts:
            break
        nxt = nxts[0]
        poly.append(nxt)
        prev, cur = cur, nxt
        if cur == start:
            break
    poly.pop()
    # collapse collinear points
    def collinear(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) == 0
    changed = True
    while changed and len(poly) > 3:
        changed = False
        m = len(poly)
        for k in range(m):
            a, b, c = poly[(k - 1) % m], poly[k], poly[(k + 1) % m]
            if collinear(a, b, c):
                poly.pop(k)
                changed = True
                break
    return poly


TARGETS = [
    ("square", [(0, 0), (8, 0), (8, 8), (0, 8)]),
    ("triangle", [(0, 0), (16, 0), (8, 8)]),
    ("rectangle", [(0, 0), (8, 8), (4, 12), (-4, 4)]),
    ("rhombus", [(0, 0), (8, 4), (16, 0), (8, -4)]),
    ("trapezoid", [(0, 0), (20, 0), (16, 4), (4, 4)]),
    ("parallelogram", [(0, 0), (16, 0), (12, 4), (-4, 4)]),
    ("house5", [(0, 0), (8, 0), (8, 6), (4, 10), (0, 6)]),
    ("Lshape", [(0, 0), (12, 0), (12, 4), (4, 4), (4, 8), (0, 8)]),
    ("boat", [(0, 0), (12, 0), (12, 4), (8, 8), (4, 8), (0, 4)]),
    ("arrow", [(0, 4), (4, 0), (4, 3), (10, 3), (10, 0), (14, 4), (10, 8), (10, 5), (4, 5), (4, 8)]),
    ("flag", [(0, 0), (2, 0), (2, 12), (0, 12)]),
    ("mountain", [(0, 0), (16, 0), (16, 2), (8, 8), (0, 2)]),
    ("diamond", [(4, 0), (12, 4), (4, 8), (-4, 4)]),
    ("table", [(0, 0), (12, 0), (12, 2), (8, 2), (8, 8), (6, 8), (6, 2), (0, 2)]),
    ("cup", [(0, 0), (8, 0), (8, 6), (6, 8), (2, 8), (0, 6)]),
    ("bow", [(0, 0), (6, 4), (0, 8), (0, 0), (10, 0), (10, 8), (0, 8)]),
    ("stair", [(0, 0), (12, 0), (12, 2), (8, 2), (8, 4), (4, 4), (4, 6), (0, 6)]),
    ("pentagon", [(0, 2), (6, -4), (12, 2), (9, 8), (3, 8)]),
]

if __name__ == "__main__":
    for name, poly in TARGETS:
        a = area(poly)
        if abs(a - 64) > 1e-6:
            print(f"{name:14} SKIP area={a}")
            continue
        res = solve(poly)
        print(f"{name:14} ok={res.get('ok')} nodes={res.get('nodes')} {res.get('error','')}")
        if res.get("ok"):
            print("  " + json.dumps(res["pieces"]))
