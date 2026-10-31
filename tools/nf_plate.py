# -*- coding: utf-8 -*-
"""The 404's plate (system, lab 31 Oct 2026): Home's Fig. 3.1 lane, engraved the same way, carrying one proposal.

The address that was asked for walks the six gates of C-072 (01 Signal, 02 Predict, 03 Decide, 04 Approve, 05 Execute,
06 Settle) and falls away at 04, the Execution Council, in red (a rejection). It never reaches the boundary, so 05 and 06
stay dashed: the drawing is the lede's "Nothing was executed." Nothing is drawn as a record: no ledger, no square
(C-191: there is no request ledger). Gate names follow C-072 (open, owner question 6): if the owner renames a gate,
change GATES here and Home's figure together.

Two drawings of the same lane, from one geometry: `nf-h` (a row, >= 700 px) and `nf-v` (a column, phones and tablets).
The labels are HTML (`.nf-keys`), laid on the stations: equal columns over x = (i - .5) / 6 of the row, equal rows
beside y = (i - .5) / 6 of the column. notfound.css draws the walk (CSS only; the still state under reduced motion and
in print is the end state); notfound.js writes the address into `[data-nf-path]` (text only)."""

GATES = [("01", "Signal", ""), ("02", "Predict", ""), ("03", "Decide", ""), ("04", "Approve", "Execution Council"),
         ("05", "Execute", "Not reached"), ("06", "Settle", "Not reached")]

# the lane's own outlines (index.html Fig. 3.1, units of its 1200 x 296 plate), centred on each station: u along the
# lane, w across it (w > 0 is "down" in the row, "right" in the column)
GATE = [(-17.1, -84.9), (17.1, -103.1), (17.1, 84.9), (-17.1, 103.1)]
COUNCIL = [(-35.1, -71.3), (35.1, -108.7), (35.1, 71.3), (-35.1, 108.7)]
BOUNDARY = [(-28.8, -84.6), (28.8, -115.4), (28.8, 84.6), (-28.8, 115.4)]
SETTLE = [(-17.1, -91.9), (17.1, -110.1), (17.1, 91.9), (-17.1, 110.1)]
REJECT_DEG = -70  # where the reject tick sits on the aperture (bottom, a little forward): the lane's red tick


def _n(v):
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else ("-0" if s == "-0.0" else s)


class Lane:
    """one orientation: `row` maps (u, w) to (x, y) = (u, w); a column maps it to (w, u)"""

    def __init__(self, row, s, along, across, spur=(50, 100), bd_shift=0):
        self.row, self.s, self.spur, self.bd_shift = row, s, spur, bd_shift
        self.along, self.across = along, across  # station positions (u) and the lane's centre line (w)

    def pt(self, cu, u, w):
        x, y = cu + u * self.s, self.across + w * self.s
        return (x, y) if self.row else (y, x)

    def poly(self, cu, pts, cls):
        p = [self.pt(cu, u, w) for u, w in pts]
        return f'<path class="{cls}" d="M{" L".join(_n(x) + " " + _n(y) for x, y in p)} Z"/>'

    def line(self, a, b):
        return f"M{_n(a[0])} {_n(a[1])} L{_n(b[0])} {_n(b[1])}"

    def hatch(self, cu, every):
        # the lane's dotted hatch: 25 strokes parallel to the gate's top edge, 7.2 apart; `every` thins them for a small plate
        d = " ".join(self.line(self.pt(cu, -16, 95.3 - 7.2 * k), self.pt(cu, 16, 78.3 - 7.2 * k)) for k in range(0, 25, every))
        return f'<path class="tk" d="{d}"/>'

    def aperture(self, cu):
        import math
        ap = lambda deg, r: (0.45 * r * math.cos(math.radians(deg)), -(0.24 * r * math.cos(math.radians(deg)) + r * math.sin(math.radians(deg))))
        ring = [self.pt(cu, *ap(a, 60)) for a in range(0, 360, 5)]
        out = [f'<path class="ln" d="M{" L".join(_n(x) + " " + _n(y) for x, y in ring)} Z"/>']
        ticks = [a for a in range(0, 360, 360 // 56 + 1)]
        ticks = [a for a in ticks if abs(((a - REJECT_DEG) + 180) % 360 - 180) > 5]
        out.append('<path class="tk2" d="' + " ".join(self.line(self.pt(cu, *ap(a, 60)), self.pt(cu, *ap(a, 69))) for a in ticks) + '"/>')
        a, b = self.pt(cu, *ap(REJECT_DEG, 58)), self.pt(cu, *ap(REJECT_DEG, 71))
        out.append(f'<path class="nf-rj" d="{self.line(a, b)}"/>')
        u0, w0 = ap(REJECT_DEG, 71)
        eu, ew = self.spur
        c1, c2, end = self.pt(cu, 27.9, 61.4), self.pt(cu, 46, 70 + (ew - 100) * .3), self.pt(cu, eu, ew)
        out.append(f'<path class="nf-spur" pathLength="1" d="M{_n(b[0])} {_n(b[1])} C{_n(c1[0])} {_n(c1[1])} {_n(c2[0])} {_n(c2[1])} {_n(end[0])} {_n(end[1])}"/>')
        dot = self.pt(cu, eu, ew + 4)
        out.append(f'<circle class="nf-fall" cx="{_n(dot[0])}" cy="{_n(dot[1])}" r="2.6"/>')
        return "".join(out), dot

    def draw(self, cls, w, h, origin, every):
        a = self.along
        o = self.pt(origin, 0, 0)
        g4 = self.pt(a[3], 0, 0)
        bd_u = (a[3] + a[4]) / 2 - 6 * self.s / 0.8 + self.bd_shift  # the boundary: just past the Council, before the rails
        rails_from, rails_to = bd_u + 34 * self.s, a[5] - 22 * self.s
        parts = [f'<svg class="{cls} lcp" viewBox="0 0 {w} {h}" width="{w}" height="{h}" fill="none" focusable="false">']
        # what lies past the Council: the boundary, five rails, the settle gate, dashed (not reached)
        parts.append(f'<g class="nf-ahead">{self.poly(bd_u, BOUNDARY, "ln")}')
        parts.append('<path class="ln" d="' + " ".join(self.line(self.pt(rails_from, 0, wv), self.pt(rails_to, 0, wv)) for wv in (-60, -30, 0, 30, 60)) + '"/>')
        parts.append(f'{self.poly(a[5], SETTLE, "ln")}</g>')
        # the line the proposal walks: a hairline from the origin to the Council, then dashed on to the settle gate
        rest_from, rest_to = self.pt(a[3] + 30 * self.s, 0, 0), self.pt(rails_from, 0, 0)
        parts.append(f'<path class="nf-rest" d="{self.line(rest_from, rest_to)}"/>')
        parts.append(f'<path class="nf-rail" pathLength="1" d="{self.line(o, g4)}"/>')
        for i in range(3):
            parts.append(f'<g class="nf-s s{i + 1}">{self.poly(a[i], GATE, "ln")}{self.hatch(a[i], every)}</g>')
        ap, dot = self.aperture(a[3])
        parts.append(f'<g class="nf-s s4">{self.poly(a[3], COUNCIL, "ln2")}{ap}</g>')
        parts.append(f'<circle class="nf-o" cx="{_n(o[0])}" cy="{_n(o[1])}" r="2.4"/>')
        parts.append(f'<circle class="nf-tok" cx="{_n(o[0])}" cy="{_n(o[1])}" r="4"/>')
        parts.append("</svg>")
        return "".join(parts), dot


def keys():
    li = []
    for n, name, sub in GATES:
        cls = ' class="is-ahead"' if sub == "Not reached" else ""
        extra = f"<small>{sub}</small>" if sub else ""
        if n == "04":
            extra += '<span class="nf-out nf-out--v" data-nf-path>this address</span>'
        li.append(f"<li{cls}><b>{n}</b> {name}{extra}</li>")
    return '<ol class="nf-keys">' + "".join(li) + "</ol>"


def plate():
    # the row: stations at (i - .5) / 6 of 1200, the origin on the grid's edge (4: the token's radius), the lane's centre
    # line at 100 (the boundary spans 8-192); the lane's own scale .8
    row = Lane(True, 0.8, [100, 300, 500, 700, 900, 1100], 100, spur=(50, 132))
    h, hdot = row.draw("nf-h", 1200, 216, 4, 1)
    # the column: 88 wide, stations 52 apart (rows of 52 px beside it), scale .375; the origin 24.96 above gate 01, so the
    # walk's stops fall at the same fractions as the row's (96 / 696 = 24.96 / 180.96: notfound.css's keyframes)
    col = Lane(False, 0.375, [26, 78, 130, 182, 234, 286], 44, spur=(40, 136), bd_shift=10)
    v, _ = col.draw("nf-v", 88, 312, 1.04, 2)
    left, top = hdot[0] / 1200 * 100, hdot[1] / 216 * 100
    out_h = f'<span class="nf-out nf-out--h" data-nf-path style="left:{left:.2f}%;top:{top:.2f}%">this address</span>'
    return ('<figure class="nf-plate" aria-hidden="true">' + keys() + '<div class="nf-draw">' + h + v + out_h + "</div></figure>")


if __name__ == "__main__":
    print(plate())
