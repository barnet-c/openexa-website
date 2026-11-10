"""The blog's plates (v2x, 30 Oct 2026): one engraved line plate per post, drawn by code in the site's plate language.

Owner: the blog group. Imported by tools/build_blog.py only. Deterministic: every random draw is seeded by the post's
slug, so a rebuild writes the same bytes.

Each plate draws the subject its post names in its own words (a drawdown, a Brownian bridge, regimes, the five stages
of the Gen-AI introduction ...), schematically: no axis carries a value, no line is the paper's data. The economics
collection keeps v2's mark (six inclined rings, one green; PG-R2-8). The post hero shows the same plate as the post's
card, captioned with a sentence quoted from the post (build_blog.py asserts each quote against the body).

Language (site.css 404 plate, Platform/Lifecycles plates): hairlines in currentColor at .2-.75 opacity, one element in
the signal green (--accent, 1.5), dashed lines for bounds and the "not yet", small filled dots for observations, hollow
dots for what is left out, vertical engraving strokes for areas. Drawn in 400 x 225 units (the cards' 16:9; written at
K = 2, viewBox 800 x 450, r4); the top 44 units stay clear for the card's label. Classes (styled in assets/css/blog.css):
  pa main line · pb secondary · pc faint (hatching, many paths) · pd dashed bound · pr base rule · pg the green line
  pk filled dot · po hollow dot · pq green dot · pt label (written on the post hero only: unlettered())
pathLength="1" on pa/pg lets CSS draw them in (the post hero at first paint; a card's green line on arrival and again on
hover or focus: build_blog.plate makes it site.css's .dm--line, hc3).
"""
import hashlib, math, random, re

W, H = 400, 225
X0, X1 = 28, 372
# r4-perf: the drawers work in 400 x 225 units; the svg is written at K times that, on an 800 x 450 viewBox, in whole
# numbers (half a drawing unit, a third of a pixel on the largest plate), so the index carries no decimals in its 25
# plates (27.4 -> ~21 KB gzip). blog.css sets the lettering in the same doubled units (--lu); since award a3 every line is a
# non-scaling stroke on site.css's whole-pixel tokens (--u = 1 px x --stroke; the green line --stroke-2).
K = 2


def rng(key):
    return random.Random(int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], 16))


def f(v):
    """a coordinate or a length as written: K times the drawing's units, a whole number"""
    return str(round(v * K))


def fr(v):
    """a dot's radius as written: K times, to a tenth (a dot is small enough for whole numbers to show)"""
    s = f"{v * K:.1f}"
    return s[:-2] if s.endswith(".0") else s


def d(xy):
    """a polyline as compact path data: the first point absolute, then relative steps, in whole written units (rounded
    once, so the relative steps cannot drift)"""
    pts = [(round(x * K), round(y * K)) for x, y in xy]
    nums = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        nums += [str(bx - ax), str(by - ay)]
    body = nums[0] + "".join(n if n.startswith("-") else " " + n for n in nums[1:]) if nums else ""
    return f"M{pts[0][0]} {pts[0][1]}l{body}"


def path(xy, cls, draw=False):
    return f'<path class="{cls}" d="{d(xy)}"' + (' pathLength="1"' if draw else "") + "/>"


def line(x1, y1, x2, y2, cls, draw=False):
    return path([(x1, y1), (x2, y2)], cls, draw)


def dot(x, y, cls="pk", r=1.6):
    return f'<circle class="{cls}" cx="{f(x)}" cy="{f(y)}" r="{fr(r)}"/>'


def label(x, y, text, anchor="middle"):
    """hero-only lettering, in sentence case (hill climb hc1: Inter in the caption register, no longer mono capitals)"""
    return f'<text class="pt" x="{f(x)}" y="{f(y)}" text-anchor="{anchor}">{text[:1].upper() + text[1:]}</text>'


def xs(n, a=X0, b=X1):
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def fit(vals, top, bottom, lo=None, hi=None):
    lo = min(vals) if lo is None else lo
    hi = max(vals) if hi is None else hi
    span = (hi - lo) or 1
    return [bottom - (v - lo) / span * (bottom - top) for v in vals]


def smooth(vals, k=2):
    out = []
    for i in range(len(vals)):
        w = vals[max(0, i - k): i + k + 1]
        out.append(sum(w) / len(w))
    return out


def walk(r, n, vol=1.0, drift=0.0, start=0.0):
    v, out = start, []
    for _ in range(n):
        out.append(v)
        v += drift + r.gauss(0, vol)
    return out


def shaped(r, n, knots, vol):
    """a walk that follows a drawn shape: knots are (t in 0..1, level); noise rides on the interpolated shape"""
    out, noise = [], 0.0
    for i in range(n):
        t = i / (n - 1)
        for (t0, a), (t1, b) in zip(knots, knots[1:]):
            if t0 <= t <= t1:
                base = a + (b - a) * (t - t0) / ((t1 - t0) or 1)
                break
        noise = noise * .82 + r.gauss(0, vol)
        out.append(base + noise)
    return smooth(out, 1)


def rule(y=204):
    return line(X0 - 4, y, X1 + 4, y, "pr")


# ---------------------------------------------------------------- financial markets research (Tim Leung)

def drawdown(r, mode):
    """price, its running peak (dashed), the distance between them hatched; green: the deepest drawdown (depth) or the
    longest stretch under water (duration)"""
    n = 96
    v = shaped(r, n, [(0, .15), (.3, .78), (.36, .7), (.42, .82), (.62, .34), (.72, .52), (.86, .74), (1, .96)], .028)
    peak, m = [], -1e9
    for a in v:
        m = max(m, a)
        peak.append(m)
    x = xs(n)
    lo, hi = min(v), max(peak)
    yv, yp = fit(v, 60, 186, lo, hi), fit(peak, 60, 186, lo, hi)
    out = [rule()]
    out += [line(x[i], yp[i], x[i], yv[i], "pc") for i in range(n) if yv[i] - yp[i] > 1.4]
    out.append(path(list(zip(x, yp)), "pd"))
    out.append(path(list(zip(x, yv)), "pa", True))
    if mode == "depth":
        i = max(range(n), key=lambda k: yv[k] - yp[k])
        out += [line(x[i], yp[i], x[i], yv[i], "pg", True), line(x[i] - 5, yp[i], x[i] + 5, yp[i], "pg"), line(x[i] - 5, yv[i], x[i] + 5, yv[i], "pg")]
        out += [label(x[i], yv[i] + 16, "drawdown")]
    else:
        best, run = (0, 0), None
        for i in range(n):
            if yv[i] - yp[i] > 1.4:
                run = i if run is None else run
                if i - run > best[1] - best[0]: best = (run, i)
            else: run = None
        a, b = max(0, best[0] - 1), min(n - 1, best[1] + 1)
        out += [path([(x[a], 196), (x[a], 200), (x[b], 200), (x[b], 196)], "pg", True)]
        out += [label((x[a] + x[b]) / 2, 216, "duration")]
    return out


def leverage(r):
    """an index and a fund built to return twice its daily returns, from the same days; dashed: where both started"""
    n = 96
    ia = [1 + v for v in shaped(r, n, [(0, 0), (.3, .1), (.55, -.12), (.8, .06), (1, .02)], .016)]
    ib = [1.0]
    for k in range(1, n):
        ib.append(ib[-1] * (1 + 2 * (ia[k] / ia[k - 1] - 1)))
    ia = [v / ia[0] for v in ia]
    lo, hi = min(ia + ib), max(ia + ib)
    x = xs(n)
    y0 = fit([1.0], 60, 190, lo, hi)[0]
    return [rule(), line(X0, y0, X1, y0, "pd"), path(list(zip(x, fit(ia, 60, 190, lo, hi))), "pa", True),
            path(list(zip(x, fit(ib, 60, 190, lo, hi))), "pg", True),
            *legend(x, ia, ib, lo, hi)]


def legend(x, ia, ib, lo, hi):
    """names on the two lines: leveraged above its peak, where the two part most in the first half; index just above its
    own line, where it has the most clear height over the word's width (hc1: under the leveraged peak, the word sat on
    the dashed start line, crossed by both)"""
    Y = lambda v: fit([v], 60, 190, lo, hi)[0]
    y0, ya, yb = Y(1.0), [Y(v) for v in ia], [Y(v) for v in ib]
    k = max(range(len(x) // 2), key=lambda j: ib[j] - ia[j])
    def room(t):   # (clear height above the index line over the word's 32 units, the line's top there)
        win = [j for j in range(len(x)) if abs(x[j] - x[t]) <= 16]
        top = min(ya[j] for j in win)
        return top - max([44] + [o for j in win for o in (y0, yb[j]) if o < ya[j] - .5]), top
    t = max((j for j in range(len(x)) if X0 + 16 <= x[j] <= X1 - 16), key=lambda j: room(j)[0])
    return [label(x[k], Y(ib[k]) - 8, "leveraged"), label(x[t], room(t)[1] - 5, "index")]


def decomposition(r, rows=3, bursts=False):
    """a price series (top) and the oscillating components it decomposes into, fastest first; green: the slowest"""
    n = 120
    t = [i / (n - 1) for i in range(n)]
    comps = []
    for k in range(rows):
        fr = (14, 6.5, 2.6, 1.1)[k] * r.uniform(.85, 1.15)
        ph = r.uniform(0, 6.28)
        env = [1 + .55 * math.sin(6.28 * (u * r.uniform(.6, 1.4) + ph)) for u in t]
        if k == rows - 1:
            c = [.9 * math.sin(6.28 * fr * u + ph) + 1.6 * u for u in t]
        else:
            c = [e * math.sin(6.28 * fr * u + ph) * (1 / (k + 1) ** .3) for u, e in zip(t, env)]
            if k == 0:
                c = [a + r.gauss(0, .18) for a in c]
                if bursts:  # volatility asymmetry: the falls are sharper than the rises
                    c = [a * (1.9 if a < 0 and .55 < u < .8 else 1) for a, u in zip(c, t)]
                c = smooth(c, 1)
        comps.append(c)
    total = [sum(c[i] for c in comps) for i in range(n)]
    x = xs(n, X0 + 10, X1)
    out = [path(list(zip(x, fit(total, 54, 98))), "pa", True)]
    band = (196 - 112) / rows
    for k, c in enumerate(comps):
        top = 112 + k * band
        out.append(line(X0, top + band * .5, X0 + 4, top + band * .5, "pr"))
        lim = max(abs(a) for a in c) if k < rows - 1 else None
        ys = fit(c, top + 3, top + band - 3, -lim if lim else None, lim)
        out.append(path(list(zip(x, ys)), "pg" if k == rows - 1 else "pb", k == rows - 1))
    out.append(line(X0, 105, X1, 105, "pr"))
    return out


def impact(r):
    """large buys (bars at the foot) and the price each one lifts; green: the lift after the largest order"""
    n = 110
    orders = sorted(r.sample(range(10, n - 14), 5))
    sizes = [r.uniform(.45, 1) for _ in orders]
    big = max(range(5), key=lambda k: sizes[k])
    p, temp, out_p = 0.0, 0.0, []
    for i in range(n):
        if i in orders:
            s = sizes[orders.index(i)]
            temp += 1.6 * s; p += .45 * s
        temp *= .86
        p += r.gauss(0, .07)
        out_p.append(p + temp)
    x = xs(n)
    ys = fit(out_p, 60, 160)
    out = [rule(198), path(list(zip(x, ys)), "pa", True)]
    for k, i in enumerate(orders):
        h = 10 + 22 * sizes[k]
        out.append(line(x[i], 198, x[i], 198 - h, "pg" if k == big else "pb", k == big))
    i = orders[big]
    out.append(line(x[i], ys[i - 1], x[i], ys[i], "pg", True))
    return out


def bridge(r):
    """paths from today to a future date, pinned to the trader's belief about the price on that date (the curve on the
    dashed line); green: one path"""
    x0, y0, xd = 40, 126, 316
    top, bot = 58, 196
    grid = [top + (bot - top) * i / 80 for i in range(81)]
    m1, m2 = r.uniform(78, 100), r.uniform(150, 176)
    dens = [math.exp(-((g - m1) / 12) ** 2) * .9 + math.exp(-((g - m2) / 15) ** 2) for g in grid]
    cdf, s = [], 0
    for v in dens:
        s += v; cdf.append(s)
    def draw_end():
        u = r.uniform(0, s)
        return next(g for g, c in zip(grid, cdf) if c >= u)
    out = [line(xd, top - 4, xd, bot + 4, "pd")]
    n = 70
    ends = [draw_end() for _ in range(12)]
    for k, e in enumerate(ends):
        w = walk(r, n, 1.0)
        pts = []
        for i in range(n):
            t = i / (n - 1)
            b = w[i] - t * w[-1]
            pts.append((x0 + (xd - x0) * t, y0 + (e - y0) * t + b * 4.2 * math.sqrt(1)))
        out.append(path(pts, "pg" if k == 0 else "pc", k == 0))
    peak = max(dens)
    out.append(path([(xd + 4 + 46 * v / peak, g) for v, g in zip(dens, grid)], "pa", True))
    out.append(dot(x0, y0, "pk", 2.4))
    out.append(label(xd, 216, "future date"))
    return out


def regimes(r):
    """a price whose drift and volatility change with the market's regime; the regime's switches at the foot (green),
    the turbulent regime hatched"""
    n = 120
    spans, i, state = [], 0, 0
    while i < n:
        L = r.randint(14, 30)
        spans.append((i, min(n, i + L), state)); i += L; state ^= 1
    v, p = [], 0.0
    for a, b, s in spans:
        for _ in range(a, b):
            p += (r.gauss(.05, .16) if s == 0 else r.gauss(-.06, .5))
            v.append(p)
    v = smooth(v, 1)
    x = xs(n)
    out = []
    for a, b, s in spans:
        if s:
            out += [line(xx, 56, xx, 168, "pc") for xx in [x[a] + k * 5 for k in range(int((x[b - 1] - x[a]) / 5) + 1)]]
    out.append(path(list(zip(x, fit(v, 64, 162))), "pa", True))
    step = []
    for a, b, s in spans:
        yy = 196 if s else 184
        step += [(x[a], yy), (x[b - 1], yy)]
    out.append(path(step, "pg", True))
    return out


def term_structures(r):
    """futures prices across maturities, one curve per date, moved by three factors (level, slope, curvature); green:
    the latest curve"""
    m = 8
    mx = [52 + k * (X1 - 64 - 52) / (m - 1) for k in range(m)]
    lvl, slp, cur = 0.0, .4, .0
    curves = []
    for _ in range(6):
        lvl += r.gauss(0, .5); slp += r.gauss(0, .35); cur += r.gauss(0, .25)
        curves.append([lvl + slp * (k / (m - 1)) * 3 + cur * math.sin(math.pi * k / (m - 1)) * 2.4 for k in range(m)])
    flat = [v for c in curves for v in c]
    lo, hi = min(flat), max(flat)
    out = [rule(), *[line(xx, 204, xx, 200, "pr") for xx in mx]]
    for j, c in enumerate(curves):
        ys = fit(c, 60, 188, lo, hi)
        pts = []
        for k in range(m - 1):  # a gentle curve through the maturities
            for s in range(6):
                t = s / 6
                pts.append((mx[k] + (mx[k + 1] - mx[k]) * t, ys[k] + (ys[k + 1] - ys[k]) * (3 * t * t - 2 * t * t * t)))
        pts.append((mx[-1], ys[-1]))
        last = j == len(curves) - 1
        out.append(path(pts, "pg" if last else "pc", last))
        if last: out += [dot(xx, yy, "pq", 2.2) for xx, yy in zip(mx, ys)]
    out.append(label(X1 - 6, 216, "maturity →", "end"))
    return out


def safe_haven(r):
    """a stock index that falls sharply and recovers, and gold (green) through the same months; dashed: where both
    started"""
    n = 100
    idx = shaped(r, n, [(0, .62), (.36, .74), (.46, .3), (.7, .58), (1, .78)], .018)
    gold = shaped(r, n, [(0, .58), (.36, .62), (.5, .78), (.7, .86), (1, .9)], .012)
    lo, hi = min(idx + gold), max(idx + gold)
    x = xs(n)
    y0 = fit([idx[0]], 60, 190, lo, hi)[0]
    return [rule(), line(X0, y0, X1, y0, "pd"), path(list(zip(x, fit(idx, 60, 190, lo, hi))), "pa", True),
            path(list(zip(x, fit(gold, 60, 190, lo, hi))), "pg", True)]


def cardinality(r):
    """assets in groups (columns); each group may hold at most k of them: the selected are filled, the rest hollow,
    the cap a dashed rule; green: one group's cap"""
    out, groups = [], 5
    gx = [72 + i * 64 for i in range(groups)]
    hot = r.randrange(groups)
    yat = lambda j: 172 - (j // 2) * 24 - (12 if j % 2 else 0)
    for gi, cx in enumerate(gx):
        cnt, k = r.randint(5, 8), r.randint(2, 3)
        for j in range(cnt):
            out.append(dot(cx + (-9 if j % 2 == 0 else 9), yat(j), "pk" if j < k else "po", 3.4 if j < k else 3.6))
        cap = yat(k - 1) - 6
        out.append(line(cx - 21, cap, cx + 21, cap, "pg" if gi == hot else "pd", gi == hot))
        out.append(path([(cx - 22, 184), (cx - 22, 189), (cx + 22, 189), (cx + 22, 184)], "pr"))
    return out


def exercise(r):
    """a share price after the vesting date (dashed), the exercise boundary that falls to the strike by maturity, and
    the moment the price first reaches it (green); after that the path is no longer the holder's"""
    n = 110
    strike = .5
    for _ in range(200):
        p = shaped(r, n, [(0, .46), (.25, .5), (.55, .68), (.8, .82), (1, .8)], .02)
        x = xs(n)
        vest = int(n * .26)
        bnd = [None] * vest + [strike + .5 * (1 - (i - vest) / (n - 1 - vest)) ** 1.5 for i in range(vest, n)]
        hit = next((i for i in range(vest, n) if p[i] >= bnd[i]), None)
        if hit and hit < n - 8: break
    lo, hi = .3, 1.02
    yp = fit(p, 60, 192, lo, hi)
    yb = fit([b for b in bnd if b is not None], 60, 192, lo, hi)
    ys = fit([strike], 60, 192, lo, hi)[0]
    out = [rule(), line(X0, ys, X1, ys, "pc"), line(x[vest], 54, x[vest], 200, "pd"),
           path(list(zip(x[vest:], yb)), "pd"), path(list(zip(x[:hit + 1], yp[:hit + 1])), "pa", True),
           path(list(zip(x[hit:], yp[hit:])), "pc"), dot(x[hit], yp[hit], "pq", 3.2), f'<circle class="pg" cx="{f(x[hit])}" cy="{f(yp[hit])}" r="{f(7)}"/>',
           label(x[vest], 216, "vesting"), label(X1, ys + 14, "strike", "end")]   # hc1: under its line (the boundary meets it above)
    return out


def mean_reversion(r):
    """three wandering prices (top) and the portfolio built from them that keeps returning to its mean (green)"""
    n = 110
    x = xs(n)
    out = [line(X0, 126, X1, 126, "pr")]
    for k in range(3):
        out.append(path(list(zip(x, fit(walk(r, n, .3, r.uniform(-.03, .05)), 58 + k * 6, 118 - (2 - k) * 6))), "pc"))
    s, ou = 0.0, []
    for _ in range(n):
        s += -.18 * s + r.gauss(0, .42)
        ou.append(s)
    ou = smooth(ou, 1)
    lim = max(abs(a) for a in ou)
    out += [line(X0, 166, X1, 166, "pd"), path(list(zip(x, fit(ou, 138, 194, -lim, lim))), "pg", True), rule()]
    return out


def shelf(r):
    """a book series on a shelf: volumes of differing size; green: the first volume"""
    out, xx, k = [rule(196)], 70.0, 0
    while xx < 318:
        w, h = r.uniform(15, 25), r.uniform(92, 132)
        cls = "pg" if k == 0 else "pb"
        out.append(path([(xx, 196), (xx, 196 - h), (xx + w, 196 - h), (xx + w, 196)], cls, k == 0))
        out += [line(xx + 3, 196 - h + 12, xx + w - 3, 196 - h + 12, "pc"), line(xx + 3, 196 - h + 16, xx + w - 3, 196 - h + 16, "pc"),
                line(xx + 3, 184, xx + w - 3, 184, "pc")]
        xx += w + r.uniform(1.5, 3.5); k += 1
    a = math.radians(-12)  # the last volume leans on the row
    w, h = 20, 112
    bx, by = xx + 2, 196
    corners = [(0, 0), (0, -h), (w, -h), (w, 0)]
    pts = [(bx + cx * math.cos(a) - cy * math.sin(a) + h * math.sin(-a), by + cx * math.sin(a) + cy * math.cos(a)) for cx, cy in corners]
    out.append(path(pts, "pb"))
    return out


def basis(r):
    """spot and futures prices (top) and the basis between them (green), which rises and falls with the season"""
    n = 120
    x = xs(n)
    season = [math.sin(6.28 * 2.4 * i / (n - 1) + r.uniform(-.2, .2)) for i in range(n)]
    spot = smooth(shaped(r, n, [(0, .4), (.4, .62), (.7, .5), (1, .7)], .014), 2)
    bas = smooth([.06 + .05 * s + r.gauss(0, .004) for s in season], 2)
    fut = [a + b for a, b in zip(spot, bas)]
    lo, hi = min(spot + fut), max(spot + fut)
    ys, yf = fit(spot, 58, 138, lo, hi), fit(fut, 58, 138, lo, hi)
    out = [line(x[i], yf[i], x[i], ys[i], "pc") for i in range(0, n, 3)]
    out += [path(list(zip(x, yf)), "pb"), path(list(zip(x, ys)), "pa", True)]
    zero = fit([0], 152, 196, -.02, .13)[0]
    out += [line(X0, zero, X1, zero, "pd"), path(list(zip(x, fit(bas, 152, 196, -.02, .13))), "pg", True), rule()]
    return out


# ---------------------------------------------------------------- AI & agents (Ajit K Dubey, 2024)

def five_stages(r):
    """the introduction's five stages, left to right: aggregative (a mass), probabilistic (a spread), deterministic (a
    line), restrictive (a line between bounds), automatic (a loop); green: the step from probabilistic to deterministic,
    the one the post says comes next"""
    cx = [58, 129, 200, 271, 342]
    cy, k_ = 120, 1.3  # k_: the figures' scale
    out = [line(X0, 170, X1, 170, "pr")] + [line(c, 166, c, 174, "pr") for c in cx]
    for _ in range(40):  # aggregative
        a, rr = r.uniform(0, 6.28), 19 * k_ * math.sqrt(r.random())
        out.append(dot(cx[0] + rr * math.cos(a), cy + rr * math.sin(a), "pk", 1.6))
    bh = lambda dx: 40 * k_ * math.exp(-(dx / (11 * k_)) ** 2)  # the bell's height dx units from its centre
    base = cy + 22 * k_
    out.append(path([(cx[1] + dx, base - bh(dx)) for dx in [(-26 + i * 1.3) * k_ for i in range(41)]], "pb"))
    for _ in range(16):  # probabilistic
        dx = max(-20 * k_, min(20 * k_, r.gauss(0, 8 * k_)))
        out.append(dot(cx[1] + dx, base - r.uniform(3, max(4, bh(dx) - 4)), "pk", 1.6))
    for k in range(7):  # deterministic
        out.append(dot(cx[2] + (-21 + k * 7) * k_, cy + (18 - k * 6) * k_, "pk", 1.9))
    out.append(line(cx[2] - 24 * k_, cy + 20.5 * k_, cx[2] + 24 * k_, cy - 20.5 * k_, "pb"))
    out += [line(cx[3] - 24 * k_, cy + 9 * k_, cx[3] + 18 * k_, cy - 27 * k_, "pd"), line(cx[3] - 18 * k_, cy + 27 * k_, cx[3] + 24 * k_, cy - 9 * k_, "pd"),
            line(cx[3] - 21 * k_, cy + 18 * k_, cx[3] + 21 * k_, cy - 18 * k_, "pa")]
    rr = 22 * k_
    out.append(f'<ellipse class="pa" cx="{f(cx[4])}" cy="{f(cy)}" rx="{f(rr)}" ry="{f(rr)}" pathLength="1"/>')
    out += [dot(cx[4] + rr * math.cos(a), cy + rr * math.sin(a), "pk", 2.2) for a in (0.3, 2.4, 4.4)]
    out.append(path([(cx[4] + rr - 3, cy - 18), (cx[4] + rr + .5, cy - 10), (cx[4] + rr + 6, cy - 17)], "pa"))
    # the bridge ("bridge the gap from probabilistic models ... to ... deterministic systems", the post's words): an arc
    # from the bell's peak to the line's last dot, the same small gap over each end (hc3: it hung over the gap, landing
    # on neither); the ends sit level, the bell's peak and that dot being at one height
    a, b, ends, top = cx[1], cx[2] + 21 * k_, cy - 30, cy - 60
    out.append(path([(a + (b - a) * t, ends - (ends - top) * 4 * t * (1 - t)) for t in [i / 24 for i in range(25)]], "pg", True))
    for i, (c, name) in enumerate(zip(cx, ("Aggregative", "Probabilistic", "Deterministic", "Restrictive", "Automatic"))):
        out.append(label(c, 189 if i % 2 == 0 else 208, name))   # hc1: two rows 19 units apart (Inter at the caption step)
    return out


def cohort(r):
    """companies in a feature space (two of its dimensions); the cohort most like the target (dashed ring); green: the
    target"""
    out, tx, ty = [], 236, 116
    for _ in range(64):
        x, y = r.uniform(X0 + 8, X1 - 8), r.uniform(60, 194)
        if (x - tx) ** 2 / 46 ** 2 + (y - ty) ** 2 / 30 ** 2 < 1.3: continue
        if tx + 54 < x < tx + 108 and ty - 54 < y < ty - 28: continue   # hc1: clear of the lettering (the word, at the caption step)
        out.append(dot(x, y, "po", 2.2))
    for _ in range(11):
        a, rr = r.uniform(0, 6.28), math.sqrt(r.uniform(.12, 1))
        out.append(dot(tx + 40 * rr * math.cos(a), ty + 25 * rr * math.sin(a), "pk", 2.4))
    out.append(f'<ellipse class="pd" cx="{f(tx)}" cy="{f(ty)}" rx="{f(50)}" ry="{f(33)}"/>')
    out += [dot(tx, ty, "pq", 3.4), f'<circle class="pg" cx="{f(tx)}" cy="{f(ty)}" r="{f(8)}" pathLength="1"/>']
    out.append(label(tx + 60, ty - 36, "cohort", "start"))
    return out


def guardrails(r):
    """a strategy held between its limits (the floor in green, the ceiling dashed) and, to the right, the tearsheet it is
    vetted on"""
    n, xa, xb = 80, X0, 262
    x = xs(n, xa, xb)
    v = shaped(r, n, [(0, .5), (.25, .66), (.45, .4), (.7, .62), (1, .7)], .045)
    v = [min(.86, max(.22, a)) for a in v]
    out = [line(xa, fit([.86], 60, 190, .1, .95)[0], xb, fit([.86], 60, 190, .1, .95)[0], "pd"),
           line(xa, fit([.22], 60, 190, .1, .95)[0], xb, fit([.22], 60, 190, .1, .95)[0], "pg", True),
           path(list(zip(x, fit(v, 60, 190, .1, .95))), "pa", True)]
    tx, ty, tw, th = 290, 62, 80, 132
    out.append(path([(tx, ty), (tx + tw, ty), (tx + tw, ty + th), (tx, ty + th), (tx, ty)], "pb"))
    mini = shaped(r, 24, [(0, .2), (.5, .6), (1, .8)], .05)
    out.append(path(list(zip(xs(24, tx + 8, tx + tw - 8), fit(mini, ty + 12, ty + 40))), "pb"))
    for k in range(6):
        yy = ty + 56 + k * 12
        out += [line(tx + 8, yy, tx + 40, yy, "pc"), line(tx + 52, yy, tx + tw - 8, yy, "pc")]
    out.append(label(tx + tw / 2, 212, "tearsheet"))
    return out


def agent(r):
    """an agent (green) on a loop that passes the parties a trade must touch (the post's own diagram, as a schematic)"""
    cx, cy, rx, ry = 200, 128, 132, 56
    out = [f'<ellipse class="pb" cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}"/>']
    for a in (math.radians(d_) for d_ in (200, 270, 340, 20, 90, 160)):
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        out.append(line(cx, cy, x, y, "pc"))
        out.append(path([(x - 6, y - 6), (x + 6, y - 6), (x + 6, y + 6), (x - 6, y + 6), (x - 6, y - 6)], "pa"))
    a0, a1 = math.radians(200), math.radians(268)
    arc = [(cx + rx * math.cos(a0 + (a1 - a0) * t / 30), cy + ry * math.sin(a0 + (a1 - a0) * t / 30)) for t in range(31)]
    out.append(path(arc, "pg", True))
    ax, ay = cx + rx * math.cos(math.radians(236)), cy + ry * math.sin(math.radians(236))
    out += [dot(ax, ay, "pq", 4), dot(cx, cy, "pk", 2.4)]
    return out


def credit(r):
    """savers (left) to a bank (green ring) to borrowers (right)"""
    cx, cy = 200, 128
    out = [f'<circle class="pg" cx="{f(cx)}" cy="{f(cy)}" r="{f(16)}" pathLength="1"/>', dot(cx, cy, "pq", 2.4)]
    for k in range(9):
        y = 66 + k * 15.5
        xl, xr = 58 + r.uniform(-6, 6), 342 + r.uniform(-6, 6)
        out += [dot(xl, y, "pk", 2.2), dot(xr, y, "po", 2.6)]
        out.append(path([(xl + 4, y), (xl + 60, y), (cx - 40, cy + (y - cy) * .25), (cx - 17, cy + (y - cy) * .08)], "pc"))
        out.append(path([(cx + 17, cy + (y - cy) * .08), (cx + 40, cy + (y - cy) * .25), (xr - 60, y), (xr - 4, y)], "pc"))
    out += [label(58, 216, "savers"), label(342, 216, "borrowers")]
    return out


# ---------------------------------------------------------------- market structure & economics (v2's mark)

RINGS = ((58, 23, -18), (86, 30, 13), (112, 46, -6), (138, 44, 17), (162, 64, -11), (186, 60, 4))  # rx, ry, tilt


def rings(turn):
    cx, cy, k_ = 212, 130, .72  # .72: the constellation keeps clear of the plate's edges and of its label
    return [f'<ellipse class="{"pg" if k == 0 else "pb"}" cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx * k_)}" ry="{f(ry * k_)}" transform="rotate({rot + turn} {f(cx)} {f(cy)})"' + (' pathLength="1"' if k == 0 else "") + "/>"
            for k, (rx, ry, rot) in enumerate(RINGS)]


# award a2 (art director, medium): the economics register's plate stands at the list's full height. The same six rings,
# one green, risen on a diagonal (the whole constellation turned RINGS_RISE degrees, each ring keeping its own tilt), so
# a tall plate is filled by the mark instead of holding a thin band of it in an empty panel; written at K like every plate.
# award a3 (art director, polish: "the drawing fills about half its frame"): the a2 sheet was a 5:8 viewBox with the
# rings at 90% of its width, so on a desk (the frame about 5:7) the drawing stood in about two-thirds of the frame each
# way. The viewBox is now the constellation's own box, taken over every angle blog.js turns it to (RINGS_STEP degrees a
# paper, as many steps as the register has rows after its first), so the sheet's margins in blog.css are the drawing's:
# it fills the frame at rest and never leaves it while it turns
RINGS_RISE, RINGS_STEP = -58, -6   # RINGS_STEP: blog.js's turn per row (--turn = -6deg x the row's index)


def _rings_box(rise):
    """the constellation's bounding box (unit scale, about its centre) when turned by rise degrees"""
    xs_, ys_ = [], []
    for rx, ry, rot in RINGS:
        a = math.radians(rot + rise)
        for i in range(360):
            t = math.radians(i)
            x, y = rx * math.cos(t), ry * math.sin(t)
            xs_.append(x * math.cos(a) - y * math.sin(a)); ys_.append(x * math.sin(a) + y * math.cos(a))
    return min(xs_), max(xs_), min(ys_), max(ys_)


def rings_tall(rows=8):
    """the rings on a sheet as tall as the register beside them (rows: its papers): a viewBox that is the constellation's
    box over its whole turn (RINGS_RISE to RINGS_RISE + RINGS_STEP x (rows - 1)), centred on the rings' common centre
    (blog.css turns the svg about its own centre), with a stroke's room at the edges"""
    w = h = 0.0
    turn = RINGS_STEP * (rows - 1)
    for t in range(0, turn - 1, -1):
        x0, x1, y0, y1 = _rings_box(RINGS_RISE + t)
        w, h = max(w, x1 - x0), max(h, y1 - y0)
    vw, vh = math.ceil(w / 2 + 1) * 2, math.ceil(h / 2 + 1) * 2   # whole even drawing units: the centre lands on a whole unit
    cx, cy = vw / 2, vh / 2
    inner = [f'<ellipse class="{"pg" if k == 0 else "pb"}" cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" transform="rotate({rot + RINGS_RISE} {f(cx)} {f(cy)})"' + (' pathLength="1"' if k == 0 else "") + "/>"
             for k, (rx, ry, rot) in enumerate(RINGS)]
    return f'<svg class="bp-art bp-rings bp-tall" viewBox="0 0 {vw * K} {vh * K}" fill="none" focusable="false" aria-hidden="true">{"".join(inner)}</svg>'


def rings_wide():
    """award a3: the economics mark where it heads its list on a phone (a 2:1 plate): the six rings lying flat, as the
    cards and the library draw them, on a viewBox that is their own box (they stood in about 45% of the card sheet's
    width there, the rest of the plate empty); written at K like every plate"""
    x0, x1, y0, y1 = _rings_box(0)
    vw, vh = math.ceil((x1 - x0) / 2 + 1) * 2, math.ceil((y1 - y0) / 2 + 1) * 2
    cx, cy = vw / 2, vh / 2
    inner = [f'<ellipse class="{"pg" if k == 0 else "pb"}" cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" transform="rotate({rot} {f(cx)} {f(cy)})"/>'
             for k, (rx, ry, rot) in enumerate(RINGS)]
    return f'<svg class="bp-art bp-rings bp-wide" viewBox="0 0 {vw * K} {vh * K}" fill="none" focusable="false" aria-hidden="true">{"".join(inner)}</svg>'


# ---------------------------------------------------------------- the register: slug -> what the plate draws

# label: the plate's name (mono, on the card and over the caption); draw: the drawer; quote: a sentence from the post
# itself that the plate draws (verbatim; build_blog.py asserts it against the body)
PLATES = {
    "in-search-gen-ai-business-model": ("Five stages", five_stages,
        "There are five stages in this progression: Aggregative, Probabilistic, Deterministic, Restrictive, and Automatic."),
    "rel-val-a-new-approach-to-relative-value-analysis-of-securities-and-cryptocurrencies": ("A cohort", cohort,
        "Through the algorithm, the N-dimensional feature space is analyzed to identify a cohort of companies with business fundamentals most similar to the target company."),
    "tearsheet-how-to-use-tearsheet-in-the-face-of-volatile-crypto-and-bond-markets-as-a-means-of-capital-preservation-and-asset-appreciation": ("Guardrails", guardrails,
        "It is crucial to implement the right guardrails, constraints, limits, and boundary conditions to protect your strategy from the volatility and uncertainties of the market."),
    "empowering-the-future-ai-copilots-and-autonomous-intelligent-agents-leading-the-way": ("An agent", agent,
        "Creating a Copilot or AI agent for financial markets is a complex and challenging endeavor."),
    "why-banks-exist-unveiling-the-vital-role-of-credit-in-the-financial-system": ("Intermediation", credit,
        "Banks serve as intermediaries between those who have excess funds (savers or depositors) and those who need funds (borrowers)."),
    "multiscale-analysis-volatility-asymmetry-of-cryptocurrency-prices": ("Mode decomposition", lambda r: decomposition(r, 3, True),
        "The HHT method can decompose any time series into oscillating components with nonstationary amplitudes and frequencies using the empirical mode decomposition (EMD)."),
    "leveraged-etfs-price-dynamics-and-options-valuation": ("Leverage ratio", leverage,
        "Within the ETF universe, some funds are designed to replicate a constant multiple (called leverage ratio) of the daily returns of a reference index."),
    "examining-the-drawdown-risk-of-sector-etfs-2022": ("Drawdown", lambda r: drawdown(r, "depth"),
        "A drawdown measures the distance (in %) of the portfolio value from its peak, reflecting its downside risk."),
    "optimal-execution-for-high-frequency-trading": ("Market impact", impact,
        "In high-frequency trading, large buy (or sell) orders may cause other traders to raise (or lower) their offered price."),
    "modern-trends-in-financial-engineering": ("A book series", shelf,
        "This new book series, Modern Trends in Financial Engineering, publishes monographs on important contemporary topics in theory and practice of Financial Engineering."),
    "stochastic-storage-cost-model-for-grains-futures": ("The basis", basis,
        "There's also a clear seasonality in the basis."),
    "dynamic-estimation-of-stochastic-gold-exposure": ("Safe haven", safe_haven,
        "Gold is often viewed as a safe haven asset or a hedge against market turmoil, currency depreciation, and other economic or political events."),
    "encoding-market-view-via-a-randomized-brownian-bridge": ("Brownian bridge", bridge,
        "Trading decisions often depend on the trader's subjective belief of the distribution of the asset price on a given future date."),
    "multiscale-decomposition-and-analysis-of-sector-etf-price-dynamics": ("Multiscale components", lambda r: decomposition(r, 4),
        "This adaptive data-driven method decomposes any time series into oscillating components with nonstationary amplitudes and frequencies."),
    "dynamic-futures-portfolio-in-a-regime-switching-market": ("Regimes", regimes,
        "Market regimes may change suddenly and persist for a period of time."),
    "dynamic-futures-portfolio-under-a-multifactor-gaussian-framework": ("Futures curves", term_structures,
        "Futures are standardized exchange-traded bilateral contracts of agreement to buy or sell an asset at a pre-determined price at a pre-specified time in the future."),
    "multiscale-financial-signal-processing": ("Multiscale factors", lambda r: decomposition(r, 3),
        "Market observations and empirical studies have shown that asset prices are often driven by multiscale factors, ranging from long-term economic cycles to rapid fluctuations in the short term."),
    "cardinality-constrained-portfolios-optimization-approach-algorithm": ("Cardinality", cardinality,
        "A cardinality-constrained portfolio caps the number of stocks to be traded within each of these groups."),
    "employee-stock-options-exercise-timing-hedging-and-valuation": ("Exercise timing", exercise,
        "This book provides a systematic overview of the contractual features of ESOs and thoughtful discussions of different valuation approaches, with emphasis on three major aspects: (i) hedging strategies; (ii) exercise timing; (iii) valuation methodologies."),
    "an-optimization-algorithm-for-sparse-mean-reverting-portfolio-selection": ("Mean reversion", mean_reversion,
        "Motivated by the industry practice of pairs trading and long/short equity strategies, we study an approach that combines statistical learning and optimization to construct portfolios with mean-reverting price dynamics."),
    "the-drawdown-risk-and-portfolio-concentration-of-sector-etfs": ("Time under water", lambda r: drawdown(r, "duration"),
        "Drawdown risk is relevant to all stocks and portfolios."),
}

# hill climb hc6 (SYSTEM.md "The hedge stamp (hc6: one rule)"): a plate that simulates data (a price path, a curve over
# a rule, a scatter: a reader could take it for the paper's figure) says "Illustrative"; a conceptual drawing (the
# stages, the loop, the flow, the shelf, the groups) and the economics rings say nothing
CONCEPTUAL = {five_stages, agent, credit, shelf, cardinality}
ILLUSTRATIVE = "Illustrative"
def stamp(slug, col):
    return "" if col == "economics" or slug not in PLATES or PLATES[slug][1] in CONCEPTUAL else ILLUSTRATIVE


PATH = re.compile(r'^<path class="(\w+)" d="([^"]+)"/>$')
DOT = re.compile(r'^<circle class="(pk|po|pq)" (cx="[^"]+" cy="[^"]+" r="[^"]+")/>$')


def compact(inner):
    """the same drawing in fewer bytes: plain paths of one class (no pathLength: they are not drawn in) become one path
    of several subpaths, and dots of one class share a group, each at the place of its class's first element (the
    painting order between classes is kept; within a class it does not matter)"""
    out, paths, dots = [], {}, {}
    for el in inner:
        m, n = PATH.match(el), DOT.match(el)
        if m:
            if m[1] not in paths: paths[m[1]] = []; out.append(("path", m[1]))
            paths[m[1]].append(m[2])
        elif n:
            if n[1] not in dots: dots[n[1]] = []; out.append(("dot", n[1]))
            dots[n[1]].append(n[2])
        else: out.append(el)
    html = []
    for el in out:
        if isinstance(el, str): html.append(el)
        elif el[0] == "path": html.append(f'<path class="{el[1]}" d="{"".join(paths[el[1]])}"/>')
        else: html.append(f'<g class="{el[1]}">' + "".join(f"<circle {a}/>" for a in dots[el[1]]) + "</g>")
    return "".join(html)


def svg(inner, cls="bp-art"):
    return f'<svg class="{cls}" viewBox="0 0 {W * K} {H * K}" fill="none" focusable="false" aria-hidden="true">{compact(inner)}</svg>'


PT = re.compile(r'<text class="pt"[^>]*>[^<]*</text>')
def unlettered(s):
    """hill climb hc1: only the post hero draws its plate's lettering; every other copy (cards, the markets panel, the
    margin plate, the library's faces, the collection plates) is written without it (CSS used to hide it there)"""
    return PT.sub("", s)


def plate_svg(slug, col, turn=0, lettering=False):
    """the plate for a post: its own drawing, or the economics rings (turned by the post's place in its collection);
    with its lettering on the post hero only"""
    if col == "economics" or slug not in PLATES:
        return svg(rings(turn), "bp-art bp-rings")
    _, fn, _ = PLATES[slug]
    out = svg(fn(rng(slug)))
    return out if lettering else unlettered(out)


NUM = re.compile(r"-?\d+(?:\.\d+)?")
INK = re.compile(r"<(path|circle|ellipse)\b([^>]*)>")
def _attr(a, name):
    m = re.search(rf'\b{name}="([^"]+)"', a)
    return m and m[1]


def ink_box(s):
    """hill climb hc2: the box of what a plate draws, in its viewBox's units, its lettering left out (the phone hides
    it): every path's points (d()'s format: an absolute start, then relative steps; compact() joins subpaths), every
    dot's and circle's extent, every ring's extent at its tilt"""
    assert not re.search(r"<(rect|line|polyline|polygon|use|image)\b", s), "ink_box measures path, circle and ellipse only"
    x0 = y0 = math.inf; x1 = y1 = -math.inf
    def take(ax, ay, bx, by):
        nonlocal x0, y0, x1, y1
        x0, y0, x1, y1 = min(x0, ax), min(y0, ay), max(x1, bx), max(y1, by)
    for tag, a in INK.findall(PT.sub("", s)):
        if tag == "path":
            for sub in _attr(a, "d").split("M")[1:]:
                head, _, steps = sub.partition("l")
                x, y = map(float, NUM.findall(head))
                take(x, y, x, y)
                ns = list(map(float, NUM.findall(steps)))
                for dx, dy in zip(ns[::2], ns[1::2]):
                    x, y = x + dx, y + dy
                    take(x, y, x, y)
        else:
            cx, cy = float(_attr(a, "cx")), float(_attr(a, "cy"))
            rx = float(_attr(a, "r") or _attr(a, "rx")); ry = float(_attr(a, "r") or _attr(a, "ry"))
            rot = _attr(a, "transform")
            t = math.radians(float(NUM.findall(rot)[0])) if rot else 0.0
            hw, hh = math.hypot(rx * math.cos(t), ry * math.sin(t)), math.hypot(rx * math.sin(t), ry * math.cos(t))
            take(cx - hw, cy - hh, cx + hw, cy + hh)
    assert x0 < x1 and y0 < y1, "a plate with nothing drawn"
    return x0, y0, x1, y1


# hc2 (4K/390 look: on a phone the hero's 16:9 drawing stood in a 5:2 frame at 44-59% of its width, the lettering that
# fills it on a desk hidden): the frame's share the drawing may take on a phone, each way, and the frame's aspect there
PHONE_FILL, PHONE_ASPECT, PHONE_ZOOM = (.84, .74), 5 / 2, 2.0
def phone_fit(s):
    """where a hero plate's svg box goes inside its 5:2 frame on a phone (blog.css, <= 640 px) so that what it draws,
    centred, fills PHONE_FILL of the frame: --fx/--fw in % of the frame's width, --fy/--fh of its height. The box keeps
    the viewBox's own shape (no letterbox), so the lines stay non-scaling hairlines and the dots grow with the drawing"""
    vw, vh = (float(v) for v in re.search(r'viewBox="0 0 (\S+) (\S+)"', s).groups())
    x0, y0, x1, y1 = ink_box(s)
    # k: frame widths per viewBox unit; the frame is 1 wide and 1 / PHONE_ASPECT tall
    k = min(PHONE_FILL[0] / (x1 - x0), PHONE_FILL[1] / PHONE_ASPECT / (y1 - y0), PHONE_ZOOM * min(.96 / vw, .94 / PHONE_ASPECT / vh))
    pct = lambda v: f"{v * 100:.2f}".rstrip("0").rstrip(".") + "%"
    return (f"--fx:{pct(.5 - k * (x0 + x1) / 2)};--fw:{pct(k * vw)};"
            f"--fy:{pct(.5 - k * (y0 + y1) / 2 * PHONE_ASPECT)};--fh:{pct(k * vh * PHONE_ASPECT)}")


def collection_svg(col):
    """the plate a collection shows once at its head on phones (where the cards drop their plates)"""
    if col == "economics": return rings_wide()
    if col == "markets": return unlettered(svg(decomposition(rng("markets"), 3)))
    return unlettered(svg(five_stages(rng("ai"))))


# ---------------------------------------------------------------- the index hero: the library (lab: blog-moment)
#
# The blog as one object: an oblong album of plates lying open, one leaf per post (29), in its three collections.
# Financial markets research (16 leaves) lies on the left, Market structure & economics (8) on the right, and the five
# AI & agents leaves stand mid-turn between them; the four Gen-AI series leaves are the green ones (the rail's four
# parts below). The top leaf of each bundle shows that collection's own plate (the plates the phones show at each
# collection's head). Drawn in 3D and projected orthographically, so every leaf is a parallelogram: one affine matrix
# places a unit square (the leaf) and the 400 x 225 drawing on it. No data: the counts are the leaves.
#
# CSS (blog.css "the library") uses the matrices the generator writes as custom properties: --k (where a turning leaf
# starts its fall at first paint) and --h (the fanned position while the pointer is on the bundle). The transform
# attribute is the rest state, so the plate is whole without CSS animation, without JS and under reduced motion.

LIB_YAW, LIB_PITCH, LIB_D = math.radians(20), math.radians(38), 225 / 400   # camera; the leaf's depth : width (16:9)
LIB_S = 300                                                                    # one leaf width in viewBox units


def _lib_proj(x, y, z):
    """yaw about the vertical, then pitch down; screen y grows downward; returns (sx, sy, depth: larger is farther)"""
    cy_, sy_ = math.cos(LIB_YAW), math.sin(LIB_YAW)
    x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_
    cp, sp = math.cos(LIB_PITCH), math.sin(LIB_PITCH)
    y, z = y * cp + z * sp, -y * sp + z * cp
    return x, -y, z


def _lib_matrix(a):
    """the leaf turned by a (radians from upright, + to the right) as (a, b, c, d, e, f) in units of LIB_S, unit square
    (s: spine -> fore-edge, t: front -> back); and the depth of its centre"""
    u = _lib_proj(math.sin(a), math.cos(a), 0)
    v = _lib_proj(0, 0, LIB_D)
    return (u[0], u[1], v[0], v[1], 0.0, 0.0), (u[2] + v[2]) / 2


def _mx(m, ox, oy):
    a, b, c, d, e, f_ = m
    return f"matrix({a * LIB_S:.2f},{b * LIB_S:.2f},{c * LIB_S:.2f},{d * LIB_S:.2f},{e * LIB_S + ox:.1f},{f_ * LIB_S + oy:.1f})"


def library_svg(counts=(16, 5, 8), lit=4):
    """the hero plate of the blog index (see the note above). Bundles are links to their collections for the pointer
    (tabindex -1; the svg is aria-hidden). award a3 (a3-ux 6): the plate carries no lettering. The collections' names
    under it (MARKETS · AI & AGENTS · ECONOMICS, in the drawing's order, not the page's) looked like tabs and did
    nothing; the names are now links under the H1 (build_blog.py), keyboard-first and in the page's order, and each
    bundle answers its link (blog.css)."""
    deg = math.radians
    # (key, angles, green leaves, face index, face drawing); angles run from the outermost leaf to the top one
    bundles = [
        # jury (blog): the leaves come from the counts, spread over the same arcs, so a new post adds a leaf
        ("markets", [deg(-88.6 + 4.4 * k / max(counts[0] - 1, 1)) for k in range(counts[0])], set(), counts[0] - 1, decomposition(rng("markets"), 3)),
        ("ai", [deg(-55 + 34 * k / max(counts[1] - 1, 1)) for k in range(counts[1])], set(range(counts[1] - lit, counts[1])), counts[1] - 1, five_stages(rng("ai"))),
        ("economics", [deg(88.6 - 4.4 * k / max(counts[2] - 1, 1)) for k in range(counts[2])], set(), counts[2] - 1, rings(0)),
    ]
    # fit: the corners of every leaf at rest and fanned (hover)
    pts = []
    for _, angs, _, _, _ in bundles:
        for a in angs + [a * 1.16 for a in angs]:
            m, _ = _lib_matrix(a)
            for s, t in ((0, 0), (1, 0), (0, 1), (1, 1)):
                pts.append((m[0] * s + m[2] * t, m[1] * s + m[3] * t))
    x0, x1 = min(p[0] for p in pts) * LIB_S, max(p[0] for p in pts) * LIB_S
    y0, y1 = min(p[1] for p in pts) * LIB_S, max(p[1] for p in pts) * LIB_S
    pad = 6
    ox, oy = -x0 + pad, -y0 + pad
    vw = round(x1 - x0 + 2 * pad)
    face_t = f"scale({1 / (W * K):.7f},{1 / (H * K):.7f}) translate(0,{H * K}) scale(1,-1)"   # plate y down -> leaf t (front at the bottom)
    groups, low = [], oy   # low: the album's lowest point at rest (the spine, or a leaf's front fore-edge corner)
    for bi, (key, angs, green, face_i, face) in enumerate(bundles):
        leaves = []
        for i, a in enumerate(angs):
            m, depth = _lib_matrix(a)
            style = ""
            if key == "ai":   # turning leaves: start their fall nearer upright; fan wider under the pointer
                style = f' style="--k:{_mx(_lib_matrix(a + deg(19))[0], ox, oy)};--h:{_mx(_lib_matrix(a * 1.16)[0], ox, oy)};--i:{len(angs) - 1 - i}"'
            inner = f'<path class="lf{" lf-g" if i in green else ""}" d="M0 0H1V1H0Z"/>'
            if i == face_i:
                mirror = f" translate({W * K},0) scale(-1,1)" if a < 0 else ""   # read from the fore-edge to the spine on the left
                inner += f'<g class="lf-face" transform="{face_t}{mirror}">{unlettered(compact(face))}</g>'
            leaves.append((depth, f'<g class="lf-w" transform="{_mx(m, ox, oy)}"{style}>{inner}</g>'))
        leaves.sort(key=lambda t: -t[0])  # far first
        low = max([low] + [_lib_matrix(a)[0][1] * LIB_S + oy for a in angs])
        groups.append(f'<a class="lib-b lib-{key}" href="#{key}" tabindex="-1">{"".join(h for _, h in leaves)}</a>')
    vh = round(low + pad)   # the album's foot: no band for lettering under it since a3 (the names are links under the H1)
    return (f'<svg class="lib-art" viewBox="0 0 {vw} {vh}" fill="none" focusable="false" aria-hidden="true">'
            + "".join(groups) + "</svg>")


# ---------------------------------------------------------------- the Gen-AI introduction's body figures (hc22)
# Hill climb hc22 (design director, item 4.3, colour; the owner's 8 Nov "full freedom", point 2, lifted S-55's "the
# Gen-AI diagrams are left"): the introduction's four figures were the site's only off-palette pictures (a Statista bar
# chart, an I/O Fund bar chart, two purple-to-cyan diagrams with ~7 px text). They are drawn here in the site's chart
# grammar instead: ink bars, the one signal-green series (the latest year; the reported growth), hairline axes, numbers
# in mono on the 14 px data step, words in Inter, on a paper sheet in the post's paper-2 mat (blog.css .bp-fig). Same
# data, same labels and credits, read off the images (data/blog_alt.json names the same values); the charts' own titles
# go (the post's captions say them), logos and licence marks go with the raster. The stage diagrams are real text
# (lists): a reader can select, find and translate them. The old files stay in assets/img/blog (build_blog copies them).
# Typos in the rasters are fixed ("Probablistic", "Algorothims", "Gaurdrails"); capitals become sentence case.
# HTML, not SVG: the words keep their size at every width (a bar chart turns into rows on a phone, a road runs down
# the page), and nothing scales below 13 px.

def _bars(groups, vmax, two=False):
    """groups: (label, [(value, green)]); a value's bar is value / vmax of the plot's bar height (blog.css --bh)"""
    out = []
    for label, vals in groups:
        cells = "".join(
            f'<span class="bpc-c{" is-g" if g else ""}" style="--v:{v / vmax:.4f}"><span class="bp-n">{t}</span>'
            f'<span class="bpc-b{" dm" if g else ""}"></span></span>' for v, t, g in vals)
        out.append(f'<span class="bpc-g"><span class="bpc-x{" bp-n" if not two else ""}">{label}</span>{cells}</span>')
    return f'<span class="bpc-p">{"".join(out)}</span>'


def _road(stages):
    return "".join(f'<li><span class="bpr-i bp-n">{n}</span><span class="bpr-h">{h}</span><span class="bpr-d">{d}</span></li>'
                   for n, h, d in stages)


INVEST = (2013, (14.6, 19.0, 25.4, 33.8, 53.7, 79.6, 95.6, 146.7, 276.1, 189.6))   # blog-095, $ billion
GROWTH = (("Microsoft", 11.5, 17.0), ("Alphabet", 11.8, 15.4), ("Meta", 17.3, 27.3), ("Amazon", 11.1, 12.5))  # blog-096, %
STAGES = ((1, "Aggregative", "Formed of separate units gathered into a mass or whole."),
          (2, "Probabilistic", "Events that have no certain outcome but have a probability."),
          (3, "Deterministic", "All events and actions are ultimately predetermined."),
          (4, "Restrictive", "Guardrail places restrictions on what the system can do."),
          (5, "Automatic", "Works on its own with little or no direct human control."))
GATES = (("01", "Data", "General purpose", 1), ("02", "LLM", "Probabilistic models", .83),
         ("03", "Algorithms", "Deterministic system", .66), ("04", "Guardrails", "Constrained system", .49))
GATE_OPEN = .31   # the fifth gate the raster left empty (a grey box, no label): drawn dashed, the plates' "not yet"


def genai_figure(key, alt):
    """the inner drawing of one of the introduction's figures (blog-095 ... blog-098), for build_blog to set in the
    figure in place of its <img> (the figure's caption stays the post's own). alt: the image's alt text, kept as the
    bar charts' accessible name (role="img"); the stage diagrams are read as their lists"""
    if key == "blog-095":
        y0, vals = INVEST
        vmax = max(vals)
        groups = [(str(y0 + i), [(v, f"{v:.1f}", i == len(vals) - 1)]) for i, v in enumerate(vals)]
        return (f'<div class="bpc" role="img" aria-label="{alt}">'
                '<span class="bp-t">Total global corporate investment in artificial intelligence* (in billion U.S. dollars)</span>'
                + _bars(groups, vmax) +
                '<span class="bp-f">* Mergers/acquisitions, minority stake investments, private investments, public offerings</span>'
                '<span class="bp-f">Source: Statista · Stanford University</span></div>')
    if key == "blog-096":
        groups = [(name, [(a, f"{a:.1f}%", False), (b, f"{b:.1f}%", True)]) for name, a, b in GROWTH]
        return (f'<div class="bpc bpc--2" role="img" aria-label="{alt}">'
                '<span class="bp-t">Q1 revenue growth <span class="bp-k"><span class="bp-sw"></span>October estimate</span>'
                '<span class="bp-k"><span class="bp-sw is-g"></span>Reported</span></span>'
                + _bars(groups, 30, two=True) + '</div>')
    if key == "blog-097":
        return ('<div class="bpr">'
                f'<div class="bpr-grp" style="--n:2"><span class="bpr-k">LLM</span><span class="bpr-road"></span>'
                f'<ol class="bpr-s" role="list">{_road(STAGES[:2])}</ol></div>'
                f'<div class="bpr-grp" style="--n:3"><span class="bpr-k">Domain</span><span class="bpr-road is-g dm"></span>'
                f'<ol class="bpr-s" role="list">{_road(STAGES[2:])}</ol></div></div>')
    if key == "blog-098":
        items = "".join(f'<li style="--h:{h}"><span class="bpg-s"><span class="bp-n">{n}</span></span>'
                        f'<span class="bpr-h">{t}</span><span class="bpr-d">{d}</span></li>' for n, t, d, h in GATES)
        return (f'<div class="bpg-w"><ol class="bpg" role="list">{items}'
                f'<li class="bpg-o" style="--h:{GATE_OPEN}" aria-hidden="true"><span class="bpg-s"></span></li></ol></div>')
    raise KeyError(key)
