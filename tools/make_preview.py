#!/usr/bin/env python3
"""Render `../preview.svg`: a grid of every level's silhouette.

Reads the puzzle data embedded in `../index.html` so the preview always
matches what the game ships.  Run from this directory:

    python3 make_preview.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load():
    html = open(os.path.join(ROOT, "index.html")).read()
    m = re.search(r'<script id="puzzles-data" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def main():
    data = load()
    cols = 6
    cw = ch = 200
    pad = 12
    rows = (len(data) + cols - 1) // cols
    W, H = cols * cw, rows * ch
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
           '<rect width="100%%" height="100%%" fill="#ffffff"/>']
    for idx, p in enumerate(data):
        x0 = (idx % cols) * cw
        y0 = (idx // cols) * ch
        xs = [q[0] for pc in p["pieces"] for q in pc["poly"]]
        ys = [q[1] for pc in p["pieces"] for q in pc["poly"]]
        mnx, mny, mxx, mxy = min(xs), min(ys), max(xs), max(ys)
        w = max(mxx - mnx, 1e-6)
        h = max(mxy - mny, 1e-6)
        sc = min((cw - 2 * pad) / w, (ch - 2 * pad - 18) / h)
        ox = x0 + (cw - w * sc) / 2
        oy = y0 + pad + (ch - 2 * pad - 18 - h * sc) / 2
        out.append('<g transform="translate(%.2f,%.2f) scale(%.4f) translate(%.4f,%.4f)" fill="#64748b">'
                   % (ox, oy, sc, -mnx, -mny))
        for pc in p["pieces"]:
            pts = " ".join("%.4f,%.4f" % (q[0], q[1]) for q in pc["poly"])
            out.append('<polygon points="%s"/>' % pts)
        out.append("</g>")
        out.append('<text x="%d" y="%d" font-family="system-ui" font-size="13" fill="#0f172a" '
                   'text-anchor="middle">%s</text>' % (x0 + cw // 2, y0 + ch - 6, p["name"]))
    out.append("</svg>")
    dst = os.path.join(ROOT, "preview.svg")
    open(dst, "w").write("\n".join(out))
    print("wrote", dst, "with", len(data), "levels")


if __name__ == "__main__":
    main()
