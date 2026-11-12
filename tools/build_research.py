import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE, og_image
from meta import HOME, ORG, WEBSITE, FEED_LINKS, ROBOTS, ld, crumbs, atom
# -*- coding: utf-8 -*-
"""Build the OpenEXA research section from openexa-research-blogs.md:
   research.html (index) + research/NN-slug.html (ten articles), in the requested order 9 · 10 · 1 … 8.
   v2x (30 Oct 2026, group "research"): the index's plate beside the list shows the pointed or read note's figure with a
   caption from that note's own words (CAPTIONS; research.js, research.css); one number per row; every note gets its
   figure caption, links to the instruments it describes (RUN) and the series disclosure (moved, words verbatim, out of
   note 02's body). Bodies, titles and read times are unchanged.
   v2x cut (1 Nov 2026, the owner: "so many words everywhere"): one heading and at most one sentence per section, then the
   drawing. The index keeps its H1, one line, the ten titles beside the plate, the blog's three collections and the
   browser instruments; the notes keep their bodies word for word and lose the kicker, the caption paragraphs, the
   labels around the end matter and the pager's summaries. The figures' labels are instrument text (<template>, set by
   figure.js when the figure draws); every hedge stays beside what it hedges. Removed lines: .shots/v2x/notes/cut-research.md."""
import html as H, io, json, math, os, re

MD = str(DATA / 'openexa-research-blogs.md')
ROOT = str(SITE)
OUT_DIR = os.path.join(ROOT, "research")
ORDER = [9, 10, 1, 2, 3, 4, 5, 6, 7, 8]
META = {  # post number → slug, figure, short label, one-line dek used on the index and cards
    9:  ("compounding-error", "horizon", "Research note", "Why long-horizon autonomous work must be decomposed into narrow agents behind a deterministic boundary."),
    10: ("post-training-and-audit", "weights", "Research note", "How a general model comes to follow one rulebook, and how a hash-chained ledger proves what it did."),
    # r3 (r3-copy moderate): five summaries restated their own titles ("Governance in Milliseconds" / "Governance in
    # milliseconds: …"). Each now says what the note covers, in its own words, and never what its figure's caption
    # already quotes beside it: 03 its two parts ("six traits a process must have before we will touch it", "Why finance
    # first"; the definition is Fig. 03's caption); 04 its second paragraph ("There is no seam where a policy can
    # intervene"; "No single agent sees the whole trade" is Fig. 04's); 07 its three parts ("One switch halts everything,
    # in every mode"); 09 its parts and its hedge ("what this does and does not show"); 10 its three phases. Wording only:
    # no claim added or made stronger (claims map, research.json). r4 (r4-copy): 09's series is one list of four
    1:  ("not-tasks-lifecycles", "lifecycle", "Series · 01", "The six traits a process must have before we will touch it, and why finance comes first."),
    2:  ("five-thousand-small-agents", "swarm", "Series · 02", "Failure analysis, not a taste for scale: an agent that sees the whole job leaves no seam where a policy can intervene."),
    3:  ("agents-decide-code-executes", "boundary", "Series · 03", "Eight layers, one boundary. The top four estimate; the bottom four are deterministic code."),
    4:  ("post-training-on-a-rulebook", "rulebook", "Series · 04", "Closing the gap between a model that knows finance and one that knows this lifecycle."),
    5:  ("the-execution-council", "council", "Series · 05", "What the Council checks, the three operating modes, and the halt that works in every mode."),
    6:  ("a-ledger-nobody-can-edit", "ledger", "Series · 06", "Append-only, hash-chained, replayable. Why a record an administrator can edit is only a claim."),
    7:  ("lifecycle-01-ten-sessions", "sessions", "Series · 07", "The setup, the result, where the cost goes, and precisely what ten sessions do not show."),
    8:  ("master-and-copy", "mastercopy", "Series · 08", "Three phases: prove one agent, master and copy it, then open the rails."),
}
# your standing rule: no exchange or broker names anywhere on the site
FIXES = [
    ("Every fill in our ten live sessions was confirmed through TradeStation or Interactive Brokers before it entered the ledger.",
     "Every fill in our ten live sessions was confirmed by the executing broker before it entered the ledger."),
    ("The execution layer routed to NASDAQ and NYSE.", "The execution layer routed each action to the venue and counterparty the routing layer scored best."),
    # 2026-10-27: a unit slip (5% a year is ~$0.0002 a day per dollar - a ten-thousandth of a dollar, not of a cent) and
    # the site-wide rule "Trillions", never $22 trillion
    ("a dollar earns roughly two ten-thousandths of a cent per day", "a dollar earns roughly two ten-thousandths of a dollar per day"),
    ("roughly seventeen thousand ETFs holding about twenty-two trillion dollars.", "roughly seventeen thousand ETFs holding trillions of dollars."),
    # 2026-10-27: the regime split follows the per-session record (Days 03-06 and 08 premium; 01, 02, 07, 09 and 10
    # discount) that the homepage and the Proof page draw from (#oxa-sessions); the source note says six and four
    ("Six sessions were in premium regimes, four in discount regimes.", "Five sessions were in premium regimes, five in discount regimes."),
]
PUBLISHED = "2026-09-21"  # the research section went live with v10 (docs/site-history.md); the markdown has no dates

# v2x (30 Oct): every figure had a caption written from its own note (PAGES.md §6.3, FC-01..FC-10).
# v2x cut (1 Nov): the figure's own labels name its parts, so the caption paragraphs (the note's quoted words) and the
# "Fig. NN" marks are gone. What stays, per formation: the line that says what is drawn (shown only on phones, in the
# index's pinned strip, where the labels do not fit) and the hedge, which stands beside every drawing.
NB = " "
CAPTIONS = {
    "horizon": ("Two runs of dependent steps, one of them gated.", "Illustrative"),
    "weights": ("One base model, rings of adapters, the record below.", "Illustrative"),
    "lifecycle": ("A lifecycle as one loop of gates, the last one lit.", "Illustrative"),
    "swarm": ("One large agent beside a lattice of small ones.", "Illustrative"),
    "boundary": ("Eight layers and one bright plane between them.", "Illustrative"),
    "rulebook": ("A dense core, with documents drifting in.", "Illustrative"),
    "council": ("Proposals arrive from above; rejected ones leave to the side.", "Illustrative"),
    "ledger": ("Eight blocks in a chain, each linked to the one before.", "Illustrative"),
    # note 09: the floor line is not a scale. Each column fills to the floor, one block per basis point, and shows ONE open
    # unit above it (the lattice below), never more; the label "above the floor / exact value not published" stays beside it
    "sessions": ("Ten sessions, one column each, in the order of the record.", "Illustrative · heights not to scale"),
    "mastercopy": ("One proven agent above, its copies below, on one control plane.", "Illustrative · roadmap"),
}
# hill climb hc23 (director item 8): on a phone the plate is a 56 px running foot, a 44 px mark and one line: what is drawn,
# a middle dot, the hedge (research.css). That line is a phrase of the caption, short enough to stand with its hedge on
# one line at 390 px (two at 320, the hedge on the second): no new fact, so each word is the caption's (or its stem's)
STRIP = {
    "horizon": "Two runs of steps, one gated",
    "weights": "One base model, rings of adapters",
    "lifecycle": "One loop of gates, the last lit",
    "swarm": "One large agent beside small ones",
    "boundary": "Eight layers, one bright plane",
    "rulebook": "A core, documents drifting in",
    "council": "Proposals arrive, rejects leave",
    "ledger": "Eight blocks in a chain",
    "sessions": "Ten sessions",
    "mastercopy": "One agent, its copies",
}
def _words(t): return re.findall(r"[a-z]+", t.lower())
for _f, _s in STRIP.items():
    _cw = _words(CAPTIONS[_f][0])
    assert all(any(c.startswith(w[:6]) for c in _cw) for w in _words(_s)), f"STRIP[{_f}]: “{_s}” uses a word its caption does not"
# hc30r (RETHINK-hc30 RES-1, "the formations redrawn: ordered marks, two tones, full size"; RES-2, note 09's ten sessions
# as Proof draws them). Every figure is a lattice of hard square marks, set where a plotter would set them: rows of
# latitude for a sphere, rings, dot grids, fused blocks. One lattice, drawn twice: here as the note's still (inline SVG:
# the hero's picture with or without JavaScript, and by reference the margin plate), and by figure.js on the index's
# plate, where the marks of one formation travel to the next. _F and the ten formations below are figure.js's F and
# FORMS, line for line (cells; x right, y down): a change to a formation there needs the same change here. A mark is
# (x, y, kind, ph, bw, bh): its top-left cell; kind 0 paper white, 1 paper white at 60 %, 2 signal green, 3 red (a
# refusal, nothing else); ph where it lies on the formation's own path (0..1, or -1); a fused block spans bw x bh cells
# (a dot is 1 x 1); a rule is bw long and bh 0; an open unit (bw < 0) is a hairline square through the centres of the
# marks at its corners. No khaki, no dust, nothing at random.
PI, TILT = math.pi, 0.36   # the spheres are seen from a little above, as Home's globe
def _Q(v): return math.floor(v * 4 + 0.5 + 1e-9) / 4   # a mark off the lattice rests on a quarter cell
def _R(v): return math.floor(v + 0.5 + 1e-9)
class _F:
    def __init__(self, w, h): self.w, self.h, self.m = w, h, {}
    def key(self, x, y): return (_R(x * 4), _R(y * 4))
    def delete(self, x, y): self.m.pop(self.key(x, y), None)
    def dot(self, x, y, k, ph=-1.0): self.m[self.key(x, y)] = (x, y, k, ph, 1, 1)
    def blk(self, x, y, bw, bh, k, ph=-1.0): self.m[self.key(x, y)] = (x, y, k, ph, bw, bh)
    def rule(self, x, y, n, k): self.m[self.key(x, y)] = (x, y, k, -1.0, n, 0)
    def open(self, x, y, bw, bh, k): self.m[self.key(x, y)] = (x, y, k, -1.0, -bw, bh)
    def run(self, x, y, n, dx, dy, k, p0=-1.0, p1=None):
        for i in range(n): self.dot(x + i * dx, y + i * dy, k, p0 if p1 is None or n < 2 else p0 + (p1 - p0) * i / (n - 1))
    def grid(self, x, y, cols, rows, dx, dy, k, ph=-1.0):
        for r in range(rows):
            for c in range(cols): self.dot(x + c * dx, y + r * dy, k, ph)
    def line(self, x0, y0, x1, y1, step, k, p0=-1.0, p1=None):
        n = max(1, math.floor(max(abs(x1 - x0), abs(y1 - y0)) / step))
        for i in range(n + 1): self.dot(_R(x0 + (x1 - x0) * i / n), _R(y0 + (y1 - y0) * i / n), k, p0 if p1 is None else p0 + (p1 - p0) * i / n)
    def ball(self, cx, cy, r, k, ph=-1.0, dy=2.0, s=2.0, avoid=()):
        """a sphere as rows of latitude: a row every dy cells down the meridian, its marks s cells apart round it; the
        near side only; no two of its marks in one half cell; none within 1.2 cells of a point of avoid (an orbit in front)"""
        nr = _R(PI * r / dy); seen = set(); ce, se = math.cos(TILT), math.sin(TILT)
        for i in range(nr):
            la = (i + 0.5) * PI / nr - PI / 2; rr = math.cos(la); n = max(1, _R(2 * PI * r * rr / s))
            for j in range(n):
                lo = (j + 0.5) * 2 * PI / n; X, Y, Z = rr * math.sin(lo), math.sin(la), rr * math.cos(lo)
                if Y * se + Z * ce < 0.03: continue
                x, y = cx + r * X, cy - r * (Y * ce - Z * se); cell = (math.floor(x * 2 + 1e-9), math.floor(y * 2 + 1e-9))
                if cell in seen or any(abs(x - ax) < 1.2 and abs(y - ay) < 1.2 for ax, ay in avoid): continue
                seen.add(cell); self.dot(_Q(x - 0.25), _Q(y - 0.25), k, ph)
    def orbit(self, cx, cy, rx, ry, rot, n, k, p0=-1.0, p1=None, hide=0.0, front=None):
        """n marks at equal steps round an ellipse turned by rot; its far half is hidden behind a ball of radius hide at
        its centre; front collects the near half's points over that ball"""
        co, si = math.cos(rot), math.sin(rot)
        for i in range(n):
            a = 2 * PI * i / n; ex, ey = rx * math.cos(a), ry * math.sin(a); x, y = ex * co - ey * si, ex * si + ey * co
            if hide and math.hypot(x, y) < hide:
                if math.sin(a) < 0: continue
                if front is not None: front.append((cx + x, cy + y))
            self.dot(_Q(cx + x - 0.25), _Q(cy + y - 0.25), k, p0 if p1 is None else p0 + (p1 - p0) * i / n)
    def marks(self): return sorted(self.m.values(), key=lambda t: (t[0], t[1]))   # the drawing order: left to right, then down
    def trim(self):
        """the box becomes the drawing's own: the marks move to its top-left corner (by whole cells, so the lattice
        stays on whole px) and w, h are where the last mark ends (a mark is half a cell; a rule has no height of its
        own). Returns the move, for the labels (figure.js make() does the same)"""
        ms = list(self.m.values()); x0, y0 = math.floor(min(m[0] for m in ms)), math.floor(min(m[1] for m in ms))
        self.m = {self.key(x - x0, y - y0): (x - x0, y - y0, k, ph, bw, bh) for x, y, k, ph, bw, bh in ms}
        self.w = max(m[0] + (abs(m[4]) - 0.5 if m[5] else m[4]) for m in self.m.values())
        self.h = max(m[1] + max(m[5], 1) - 0.5 for m in self.m.values())
        return x0, y0
def _horizon():   # 01: a monolithic run decays as p to the n; a gated run is caught at every gate and stays high
    f = _F(91, 56)
    f.run(0, 54, 46, 2, 0, 1)
    ys = [_R(52 - 46 * math.pow(0.986, c * 160 / 90)) for c in range(92)]
    for c in range(91):
        for y in range(ys[c], max(ys[c] + 1, ys[c + 1] - 1) + 1): f.dot(c, y, 0, c / 90)
    for s in range(11): f.run(s * 9, 0, 13, 0, 1, 1, s / 10)
    for c in range(91):
        if c % 9 == 0: continue
        y = 6 + _R(4 * (c % 9 - 1) / 7); f.dot(c, y, 2, c / 90); f.dot(c, y + 1, 2, c / 90)
    return f
def _weights():   # 02: one base model, rings of adapters, the record below
    f = _F(84, 55); cx, cy, fr = 42.25, 22.25, []
    f.orbit(cx, cy, 31, 7, -0.42, 104, 1, 0.0, 0.5, 17.5, fr)
    f.orbit(cx, cy, 30, 11, 0.5, 108, 2, 0.0, 0.5, 17.5, fr)
    f.orbit(cx, cy, 27, 3.5, 0.05, 88, 1, 0.0, 0.5, 17.5, fr)
    f.ball(cx, cy, 17, 0, -1.0, 2.0, 2.0, fr)
    for b in range(5):
        x = 12 + b * 13; p = 0.55 + b * 0.1
        f.run(x, 45, 9, 1, 0, 2, p); f.run(x, 50, 9, 1, 0, 2, p); f.run(x, 46, 4, 0, 1, 2, p); f.run(x + 8, 46, 4, 0, 1, 2, p)
        f.run(x + 2, 47, 5, 1, 0, 2, p)
        if b: f.run(x - 3, 48, 2, 1, 0, 2, p - 0.05)
    return f
def _lifecycle():   # 03: one loop of six gates, agents on its middle track, the last gate lit
    f = _F(92, 56); cx, cy, rx, ry, a0 = 46.25, 28.25, 42, 24, -5 * PI / 6
    gates = [(_R(cx + rx * 0.92 * math.cos(a0 + n * PI / 3) - 2.25), _R(cy + ry * 0.86 * math.sin(a0 + n * PI / 3) - 2.25)) for n in range(6)]
    for t in range(3):
        n = 156 - t * 14; sx, sy = 1 - t * 0.08, 1 - t * 0.14
        for i in range(n):
            a = a0 + 2 * PI * i / n; x, y = _Q(cx + rx * sx * math.cos(a) - 0.25), _Q(cy + ry * sy * math.sin(a) - 0.25)
            if any(gx - 2 < x < gx + 6 and gy - 2 < y < gy + 6 for gx, gy in gates): continue
            f.dot(x, y, 0 if t == 1 else 1, min(1.0, i / n * 6 / 5.4))
    for n, (x, y) in enumerate(gates):
        if n == 5: f.blk(x, y, 5, 5, 2, 1.0)
        else: f.grid(x, y, 5, 5, 1, 1, 0, n / 5.4)
    return f
def _swarm():   # 04: one large agent beside a lattice of small ones, each with its gate
    f = _F(92, 48)
    f.ball(21.25, 23.25, 21, 1)
    for gy in range(7):
        for gx in range(7):
            x, y = 50 + gx * 6, 5 + gy * 6; p = (gx + gy) / 12
            f.grid(x, y, 2, 2, 1, 1, 0, p); f.run(x + 3, y, 2, 0, 1, 2, p)
    return f
def _boundary():   # 05: eight layers, one boundary: agents decide above the bright plane, code executes below
    f = _F(70, 71)
    for l in range(8):
        y0 = l * 8 + (9 if l > 3 else 0); p = (l + (1 if l > 3 else 0)) / 9
        for d in range(5): f.run(4 + (4 - d) * 2, y0 + d, 27, 2, 0, 0 if l < 4 else 1, p)
    for d in range(5): f.run((4 - d) * 2, 33 + d, 62, 1, 0, 2, 4 / 9)
    return f
def _rulebook():   # 06: a dense cube with a lit core, six documents drifting in
    f = _F(88, 52)
    for d in range(1, 6): f.run(35 + d, 17 - d, 19, 1, 0, 1, 0.96); f.run(53 + d, 18 - d, 18, 0, 1, 1, 0.96)
    f.grid(35, 17, 19, 19, 1, 1, 0, 0.96)
    for yy in range(23, 30):
        for xx in range(41, 48): f.delete(xx, yy)
    f.blk(41, 23, 7, 7, 2, 0.96)
    for i in range(6):
        x, y = (3 if i < 3 else 78), 3 + (i % 3) * 18
        f.run(x, y, 7, 1, 0, 0, 0.08); f.run(x, y + 8, 7, 1, 0, 0, 0.08); f.run(x, y + 1, 7, 0, 1, 0, 0.08); f.run(x + 6, y + 1, 7, 0, 1, 0, 0.08)
        for r in (2, 4, 6): f.run(x + 2, y + r, 3, 1, 0, 0, 0.08)
        f.line(x + 9 if i < 3 else x - 3, y + 4, 32 if i < 3 else 61, 26 + ((i % 3) - 1) * 6, 2, 1, 0.12, 0.9)
    return f
def _council():   # 07: proposals arrive from above, approved go on down to the record, rejected leave to the side
    f = _F(82, 60); cx = 38
    for r in range(8):
        for j in range(8 - r): f.dot(cx - (7 - r) * 2 + j * 4, r * 2, 1, r / 7 * 0.4)
    for rr, n in ((13, 60), (10, 46), (7, 32)): f.orbit(cx + 0.25, 30.25, rr, rr, 0, n, 0, 0.42)
    f.run(cx, 45, 10, 0, 1, 2, 0.46, 0.9)
    f.run(22, 56, 33, 1, 0, 2, 0.92); f.run(22, 57, 33, 1, 0, 2, 0.92)
    f.run(cx + 15, 30, 8, 2, 0, 3, 0.46, 0.9)
    f.grid(69, 29, 3, 3, 1, 1, 3, 0.9)
    return f
def _ledger():   # 08: eight blocks in a chain, each holding the hash of the one before
    f = _F(86, 55)
    for b in range(8):
        x, y = b * 11, 1 + b * 7
        if b == 7: f.blk(x, y, 9, 5, 2, b / 8)
        else: f.grid(x, y, 9, 5, 1, 1, 0, b / 8)
        if b: f.run(x - 7, y - 1, 4, 0, 1, 2, (b - 1) / 8, (b - 0.5) / 8); f.run(x - 6, y + 2, 5, 1, 0, 2, (b - 0.5) / 8, b / 8)
    return f
def _sessions():
    """09 (RES-2: "the note's ten sessions are Proof's ten columns"): ten blocks to the floor, one per basis point, and one
    open unit above it, a hairline square as on Proof: how far above the floor a session went is not published, so
    nothing taller is drawn (the site's rule for every picture of this record). The floor and the 0 line are rules"""
    f = _F(76, 46)
    for c in range(10):
        x = c * 8
        f.open(x, 0, 4, 4, 2)
        for r in range(10): f.blk(x, 5 + r * 4, 4, 4, 2)
    f.rule(-1, 4, 78, 0); f.rule(-1, 45, 78, 1)
    return f
def _mastercopy():   # 10: one proven agent, its copies below on one bus, one control plane
    f = _F(92, 66)
    f.ball(46.25, 11.25, 11, 2, 0.04, 1.5, 1.5)
    f.run(46, 24, 4, 0, 1, 1, 0.1, 0.2)
    f.run(10, 28, 73, 1, 0, 1, 0.2, 0.2)
    for c in range(5):
        x = 10 + c * 18
        f.run(x, 29, 4, 0, 1, 1, 0.3, 0.6); f.ball(x + 0.25, 40.25, 6, 1, 0.74, 1.5, 1.5)
    f.run(0, 60, 92, 1, 0, 1, 0.9)
    return f
FORM = {"horizon": _horizon(), "weights": _weights(), "lifecycle": _lifecycle(), "swarm": _swarm(), "boundary": _boundary(),
        "rulebook": _rulebook(), "council": _council(), "ledger": _ledger(), "sessions": _sessions(), "mastercopy": _mastercopy()}
RAW = {fig: f.marks() for fig, f in FORM.items()}    # the marks as the formations place them (PARTS selects by these)
MOVE = {fig: f.trim() for fig, f in FORM.items()}    # then each box is trimmed to its drawing; the labels move with it
# v2x lab (research moment): every figure is read as a plate. Its labels pin to points of the formation (figure.js sets
# each at data-at, the formation's own cells) and say what each part is, in the words of its caption or its note: no new
# fact, no number the caption does not already state. Points are the lattice's (above): a formation that moves needs
# its labels moved here. Sides: r, l (text beside the point, its first line on the rule), t, b (centred above, below),
# tl, tr, bl, br (above or below, text ending or starting at the point). Flags: "minor" (dropped on a small stage),
# "minorsub" (its second line, a gloss, dropped on a small stage; never for a hedge), "acc" (the green part), "rej" (a
# rejection: the only red text), "n" (a numeral alone, as note 09's axis: mono, as a paper plate's .hp-lab--n), "nsub"
# (its second line a value, "10 bps": mono). The words are the paper plates' caption register (research.css .fl-t:
# Inter, sentence case). An optional last item is where the words begin when the point lies inside the drawing: the
# rule reaches out to it (figure.js data-to, --lead).
# Path: the span of the formation's own path (the marks' ph, 0..1) the label names; while the light walks the path it
# lights each label it passes, so the plate reads itself out in the note's order. None: the part is not on the path.
# r3 (r3-a11y moderate): "keep" marks a label that carries a hedge (note 09 "exact value not published", note 10 "phase
# two, on the roadmap"). It is listed first, so where words would cross, the claim-side label yields to it; where its
# own side has no room (a phone's stage), figure.js looks for another free slot round its point; and if there is none,
# the plate shows no labels at all, so a drawing never names its parts without their hedge (data-keep). "keep=t,tl,tr"
# limits the slots to those sides: "above the floor" never stands below the columns it describes.
def _cols():  # note 09: the ten columns' numbers, under the 0 line, in the record's order (the drawing's axis: one row)
    return [(f"{c + 1:02d}", None, (c * 8 + 1.75, 46.25), "b", "n" if c in (0, 9) else "minor n", None) for c in range(10)]
def _gate(n, dy):  # note 03: gate n of the loop (its block is five cells): the middle of its head (dy -1) or its foot (dy 5.5)
    a = -5 * PI / 6 + n * PI / 3
    return (_R(46.25 + 42 * 0.92 * math.cos(a) - 2.25) + 2.25, _R(28.25 + 24 * 0.86 * math.sin(a) - 2.25) + dy)
LABELS = {
    "horizon": [("Verification gate", None, (45.25, 13.5), "b", "", (0.5, 0.5)),
                ("A gate after every step", None, (72.25, -1), "t", "acc", (0.75, 0.85)),
                ("p to the power n", None, (80.25, 44.5), "t", "", (0.86, 0.92))],  # p, the note's variable, keeps its case
    "weights": [("One base model", None, (42.25, 3.5), "t", "", None),
                ("Adapters", None, (70.75, 8.25), "t", "", (0.0, 0.5)),
                ("The record", "Each holds the previous hash", (42.25, 52), "b", "minorsub", (0.55, 0.95))],
    # the note's own definition of a lifecycle, in its order round the loop
    # "Signal" and "Record" stand off the loop's corners (tl, bl): centred over their gates, their words lay on the outer track
    "lifecycle": [("Signal", None, _gate(0, -1), "tl", "", (0.0, 0.03)),
                  ("Decisions, approvals", None, _gate(1, -1), "t", "", (0.18, 0.56)),
                  ("Executes against an external counterparty", None, _gate(4, 5.5), "b", "minor", (0.74, 0.74)),
                  ("Record", None, _gate(5, 5.5), "bl", "acc", (0.93, 1.0))],
    "swarm": [("One large agent", None, (21.25, 1), "t", "", None),
              ("One gate, one job each", None, (70.25, 1), "t", "acc", None)],
    "boundary": [("01–04 Decide", None, (2.75, 12.25), "l", "", (0.0, 0.34)),
                 ("The boundary", None, (2.75, 35.25), "l", "acc", (0.44, 0.44)),
                 ("05–08 Execute", None, (2.75, 53.25), "l", "", (0.55, 0.89))],   # hc30r: no gloss ("Deterministic code"): its room cost the stack a seventh of its size, and the title says it
    "rulebook": [("Documents, exceptions", None, (81.25, 1.5), "t", "", (0.08, 0.2)),
                 ("The post-trained model", None, (47.25, 10.5), "t", "", (0.96, 0.96))],
    # "Proposals" stands over them (beside them it had no room on a phone, and the first step went unnamed there)
    "council": [("Proposals", None, (38.25, -0.25), "t", "", (0.0, 0.1)),
                ("Execution Council", None, (24, 30.5), "l", "", (0.42, 0.42)),
                ("Approved", None, (37, 49.75), "l", "acc", (0.6, 0.9)),
                ("Rejected, logged", None, (70.25, 33), "b", "rej", (0.9, 0.9))],
    "ledger": [("Record 01", None, (4.25, 0), "tr", "", (0.0, 0.06)),
               # on the link between records 04 and 05, its words in the empty corner under the chain
               ("Hash of the previous record", None, (37.25, 32.5), "bl", "", (0.4, 0.5)),
               ("Newest", None, (81.25, 55.5), "b", "acc", (0.875, 0.9))],
    # the floor is read like an axis, named at the rule's left end, the first line on the rule: the site's one order for
    # it, the word then its value ("Floor" over "10 bps", as Proof's Fig. 1.1 and Home's overture). Each hedge label
    # first ("keep", above): "Above the floor" points at the top of the one open unit each column carries. The columns
    # stand on a 0 line, as on Proof (its "0" in mono at the rule's left end)
    "sessions": [("Above the floor", "Exact value not published", (37.75, -0.75), "t", "keep=t,tl,tr", None),
                 ("Floor", "10 bps", (-1, 4.25), "l", "nsub", None),
                 ("0", None, (-1, 45.25), "l", "n", None)] + _cols(),
    # the copies' hedge stands under them, in the room above the control plane: the one place it has at every size
    "mastercopy": [("Copies", "Phase two, on the roadmap", (46.25, 47.25), "b", "keep=b", (0.74, 0.74)),
                   ("Master agent", None, (58.5, 11.25), "r", "acc", (0.0, 0.06)),
                   ("One control plane", None, (0.25, 61.5), "br", "", (0.9, 0.9))],
}
LABELS = {fig: [(l[0], l[1], (l[2][0] - MOVE[fig][0], l[2][1] - MOVE[fig][1])) + tuple(l[3:6]) + tuple((t[0] - MOVE[fig][0], t[1] - MOVE[fig][1]) for t in l[6:])
                for l in ls] for fig, ls in LABELS.items()}
def _keep(flags): return next((f for f in flags.split() if f.split("=")[0] == "keep"), None)
def _small(sub, fl):
    """a label's second line: a gloss (minorsub: dropped on a small stage) or a value (nsub: mono, as .hp-lab--n)"""
    if not sub: return ""
    c = ' class="fl-minor"' if "minorsub" in fl else ' class="fl-v"' if "nsub" in fl else ""
    return f"<small{c}>{H.escape(sub, quote=False)}</small>"
assert all(not _keep(l[4]) for ls in LABELS.values() for l in ls[1:]), "a hedge label (keep) is listed first"
# a label's words in CSS px (research.css .fl / .fl-t: Inter at --fs-small, 14 px at 1440; a numeral alone or a value
# line (n, nsub) 11 px mono, an advance of .64 em with the tracking; 1.35 leading; the rule's 19 px lead beside the
# point, 18 px above or below it, the tl/tr words 6 px past it). Inter's advances (thousandths of an em, measured in
# Chromium from the vendored inter-var-latin.woff2; digits at their tabular width; kerning only narrows a word, so the
# box is never short)
_FS, _FN = 14, 11
_ADV = {**dict(zip("abcdefghijklmnopqrstuvwxyz", (562, 612, 571, 612, 583, 370, 613, 591, 242, 242, 549, 242, 876, 591, 600, 612,
                                                 612, 376, 528, 327, 591, 562, 818, 546, 562, 552))),
        **dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (690, 654, 730, 722, 601, 590, 746, 743, 269, 571, 672, 565, 903, 753, 765, 639,
                                                 765, 644, 642, 646, 744, 690, 985, 682, 679, 629))),
        **{c: 650 for c in "0123456789"}, " ": 281, " ": 281, ",": 288, ".": 288, "-": 460, "–": 500}
# a mono line is measured at 13 px, its size on a phone (research.css: --fs-small under 600 px), where the room is scarcest:
# at 11 px note 09's "10 bps" had 8 px too little there, and "Floor" slid onto its own rule
def _tw(t, mono=False): return len(t) * 0.64 * 13 if mono else sum(_ADV.get(c, 1000) for c in t) / 1000 * _FS
def _lsize(lab, plate=False):
    """a label's words: (width, height, the em its first line is set in), px at 1440"""
    text, sub, _at, _side, flags = lab[:5]; fl = flags.split()
    if "minorsub" in fl and plate: sub = None
    em = _FN if "n" in fl else _FS
    return max(_tw(text, "n" in fl), _tw(sub, "nsub" in fl) if sub else 0), 1.35 * em + (1.35 * (_FN if "nsub" in fl else _FS) if sub else 0), em
def _lbox(side, ax, ay, w, h, em=_FS, lead=19):
    if side in ("r", "l"):  # the first line on the rule (research.css: translate(.., -.675em))
        x0 = ax + lead if side == "r" else ax - lead - w
        return x0, ay - 0.675 * em, x0 + w, ay - 0.675 * em + h
    y0 = ay - 18 - h if side[0] == "t" else ay + 18
    x0 = ax - w / 2 if len(side) == 1 else ax + 6 - w if side[1] == "l" else ax - 6
    return x0, y0, x0 + w, y0 + h
def _pads(fig):
    """the room a formation's labels take outside its box, (top, right, bottom, left) in rem: research.css takes it from
    the stage before it sizes the lattice's cell (.fg), so the words named here have their place at any size. Words
    above or below the box take its height; words beside it their width (words above or below slide along the box, so
    their width takes none). Measured with the cell at 4 px and at 8 (a point outside the box moves out with the cell;
    a point inside it moves in)"""
    f = FORM[fig]; t = r = b = l = 0.0
    for lab in LABELS[fig]:
        w, h, em = _lsize(lab)
        for K in (4, 8):
            x0, y0, x1, y1 = _lbox(lab[3], lab[2][0] * K, lab[2][1] * K, w, h, em)
            if lab[3] not in ("l", "r"): t, b = max(t, -y0), max(b, y1 - f.h * K)
            elif "minor" not in lab[4].split(): l, r = max(l, -x0), max(r, x1 - f.w * K)   # dropped on a small stage, where the width matters
    return tuple(math.ceil(v + 6) / 16 if v > 0 else 0 for v in (t, r, b, l))
PADS = {fig: _pads(fig) for fig in FORM}
def _rem(v): return f"{v:g}rem"
def labels_html(fig, pad=False):
    """a figure's labels, for figure.js (instrument text: nothing shows them until the figure is drawn). pad: the room
    they take (the index's plate, whose box figure.js sizes for each formation; a hero's is in its markup)"""
    out = []
    for i, (text, sub, (x, y), side, flags, path, *to) in enumerate(LABELS[fig]):
        k = _keep(flags)
        cls = "".join(f" fl--{f}" for f in flags.split() if not f.endswith("sub") and f != k)
        keep = (f' data-keep="{k.partition("=")[2].replace(",", " ")}"' if "=" in k else " data-keep") if k else ""
        small = _small(sub, flags.split())
        ph = f' data-ph="{path[0]:g},{path[1]:g}"' if path else ""
        reach = f' data-to="{to[0][0]:g},{to[0][1]:g}"' if to else ""
        out.append(f'<span class="fl{cls}" data-at="{x:g},{y:g}"{reach} data-side="{side}"{ph}{keep} style="--i:{i}"><span class="fl-t">{H.escape(text, quote=False)}{small}</span></span>')
    room = f' data-pad="{" ".join(_rem(v) for v in PADS[fig])}"' if pad else ""
    return f'<template data-labels><div class="fig-labels" data-for="{fig}"{room} aria-hidden="true">{"".join(out)}</div></template>'
# hc29 (the director's HC29 item 12, visuals and consistency: "two books in two techniques on sibling pages, the particle
# one the softer"): the index hero's book is engraved as the blog index's library is (blog_plates.library_svg): every leaf
# one affine image of a unit square under an orthographic camera, an ink fill that hides what lies behind it, a hairline
# rim on --stroke (non-scaling: 1 px at 1440, 2 at 3840, as crisp at DPR 1 as at 2), the lit leaves in the signal green,
# hatching on the faces at .2. Not the blog's object: the blog's album lies open with its leaves turning; this book stands
# open, ten leaves round one upright spine, one leaf per note, opened between the two research notes (01-02, the green
# leaves, on the left) and the series (03-10, fanned to the right): the index's own gap between 02 and 03. The open spread
# shows a page of type (the notes' measure, drop cap and paragraphs, drawn as rules; no words). No data: the leaves are
# the notes. It replaces r2's ruled still under figure.js's 'library' points (WebGL, soft at DPR 1), so the hero starts no
# WebGL and is the same drawing without JavaScript, without WebGL and under reduced motion. Its two keys are v2's leaders,
# in the words of the index's two section heads, pinned to the head of leaf 01's and leaf 10's fore-edges.
BOOK_YAW, BOOK_PITCH = math.radians(-38), math.radians(24)   # the camera: from the reader's left, a little above
BOOK_H, BOOK_S = 1.25, 200                                    # a page's height : its width (spine to fore-edge); the width in units
BOOK_ANGLES = (-82, -72) + tuple(5 + 75 * k / 7 for k in range(8))   # each leaf from the line of sight, degrees, 01 .. 10
BOOK_SHUT = BOOK_ANGLES[-1]   # on arrival the series' leaves fan out from the last one, shut on it (research.css rs-fall)
BOOK_KEYS = (("01–02 Research notes", 0, "acc", "tl"), ("03–10 The series", 9, "", "t"))   # (words, leaf, flag, side) at the
# head of the leaf's fore-edge; 01-02 stands up and to the left of its point, clear of the green leaf's head rising to
# the spine. On a phone there is no room left of the book: 01-02 hangs from the foot of the same edge (data-foot)
def _bk(a):
    """leaf a (radians) as a matrix (a, b, c, d) in units, (s, t) = (spine -> fore-edge, foot -> head) to the screen, y down;
    and its depth (larger is nearer the eye) at the leaf's centre"""
    ya, pa = BOOK_YAW, BOOK_PITCH
    R = (math.cos(ya), 0.0, -math.sin(ya))
    U = (-math.sin(ya) * math.sin(pa), math.cos(pa), -math.cos(ya) * math.sin(pa))
    D = (math.sin(ya) * math.cos(pa), math.sin(pa), math.cos(ya) * math.cos(pa))
    dot = lambda p, q: p[0] * q[0] + p[1] * q[1] + p[2] * q[2]
    u, v = (math.sin(a), 0.0, math.cos(a)), (0.0, BOOK_H, 0.0)
    return (dot(u, R) * BOOK_S, -dot(u, U) * BOOK_S, dot(v, R) * BOOK_S, -dot(v, U) * BOOK_S), dot(u, D) / 2 + dot(v, D) / 2
def _bk_page(recto):
    """a page of type in the leaf's own square, as rules: the measure between the gutter (s .14) and the fore-edge (s .9),
    read from the gutter on a recto and from the fore-edge on a verso. The recto opens a note: two title rules, then a
    three-line drop cap (four engraved strokes) and two paragraphs; the verso is text from head to foot"""
    g, f, lead, cap = 0.14, 0.9, 0.047, 0.115
    def rule(t, a, b):   # a, b: along the measure from its start, 0-1
        x = (lambda k: g + (f - g) * k) if recto else (lambda k: f - (f - g) * k)
        return f"M{x(a):.3f} {t:.3f}H{x(b):.3f}"
    out = []
    if recto:
        out += [rule(0.875, 0, 0.62), rule(0.875 - lead, 0, 0.36)]
        top = 0.875 - 3.4 * lead
        out += [f"M{g + cap * k / 3:.3f} {top + 0.012:.3f}V{top - 2 * lead - 0.006:.3f}" for k in range(4)]
        ends = (1, 1, 1, 1, 0.97, 1, 0.58, None, 1, 1, 0.98, 1, 1, 0.44)
    else:
        top = 0.875
        ends = (1, 0.99, 1, 1, 0.71, None, 1, 1, 1, 0.98, 1, 1, 1, 1, 1, 0.6)
    ind = 0
    for i, e in enumerate(ends):
        if e is None: ind = 0.06; continue      # a paragraph's end: the next line is indented
        a = (cap + 0.035) / (f - g) if recto and i < 3 else ind
        out.append(rule(top - i * lead, a, e)); ind = 0
    return '<path class="pc" d="' + "".join(out) + '"/>'
def library_svg():
    """the index hero's book (the note above): (svg, the keys' html, the box's aspect ratio). Units: a page's width is
    BOOK_S; the viewBox is the book's own box, so the keys are placed in % of it and
    research.css's .rs-bk keeps its shape (--bk-r, on the hero: the phone's hero keeps the book's height at its foot)"""
    leaves = [(_bk(math.radians(deg))[1], l, _bk(math.radians(deg))[0]) for l, deg in enumerate(BOOK_ANGLES)]
    ms = [m for _, _, m in leaves]
    corners = [(m[0] * s + m[2] * t, m[1] * s + m[3] * t) for m in ms for s in (0, 1) for t in (0, 1)]
    pad = 3
    x0, x1 = min(c[0] for c in corners) - pad, max(c[0] for c in corners) + pad
    y0, y1 = min(c[1] for c in corners) - pad, max(c[1] for c in corners) + pad
    vw, vh = round(x1 - x0), round(y1 - y0)
    ox, oy = -x0, -y0   # the spine's foot in the viewBox
    mx = lambda m: f"matrix({m[0]:.2f},{m[1]:.2f},{m[2]:.2f},{m[3]:.2f},{ox:.1f},{oy:.1f})"
    out = []
    for depth, l, m in sorted(leaves):   # far first: each leaf's fill hides what lies behind it
        face = _bk_page(True) if l == 2 else _bk_page(False) if l == 1 else ""
        style = ""
        if l > 1:   # the series fans out from the shut leaf 10, as pages let fall: 03 first, the furthest, then 04 .. 09
            style = f' style="--k:{mx(_bk(math.radians(BOOK_SHUT))[0])};--i:{l - 2}"'
        out.append(f'<g class="lf-w{" bk-s" if l > 1 else ""}" transform="{mx(m)}"{style}>'   # lf-w: the blog library's leaf (and site.css's off-screen pause)
                   f'<path class="lf{" lf-g" if l < 2 else ""}" d="M0 0H1V1H0Z"/>{face}</g>')
    svg = (f'<svg class="rs-still" viewBox="0 0 {vw} {vh}" fill="none" focusable="false" aria-hidden="true">'
           + "".join(out) + "</svg>")
    keys = []
    for i, (words, l, flag, side) in enumerate(BOOK_KEYS):
        m = _bk(math.radians(BOOK_ANGLES[l]))[0]
        x, y = m[0] + m[2] + ox, m[1] + m[3] + oy   # (s, t) = (1, 1): the head of the fore-edge
        pct = lambda v, n: f"{100 * v / n:.2f}%"
        foot = f' data-foot style="--x:{pct(x, vw)};--y:{pct(y, vh)};--fx:{pct(m[0] + ox, vw)};--fy:{pct(m[1] + oy, vh)};--i:{i}"' if side == "tl" else f' style="--x:{pct(x, vw)};--y:{pct(y, vh)};--i:{i}"'
        keys.append(f'<span class="fl{" fl--" + flag if flag else ""}" data-side="{side}"{foot}>'
                    f'<span class="fl-t">{H.escape(words, quote=False)}</span></span>')
    return svg, f'<div class="rs-keys">{"".join(keys)}</div>', f"{vw / vh:.4f}"
# The stills. A formation's marks as SVG paths in its own cells (research.css .fs-still, .mk): a run of three or more
# marks one cell apart is one stroke dashed at the lattice's pitch (.r; two cells apart .r2), every other mark a
# zero-length stroke (.d), a fused block a filled path (.b), a rule a hairline (.l), an open unit a hairline square
# (.o). The stroke is the mark (square caps, non-scaling: a whole number of px, research.css --m), so the still is the
# lattice figure.js draws on the index's plate, at any size.
# A hero's still is also what moves (lit): its marks on the formation's path are set in LIT steps of that path (.pt,
# --p: where the step lies, 0..1), and research.css lets each stand a step larger as the pass of light reaches it
# (.is-pass, set once by figure.js): one drawing, no second renderer over it. `pt` is a name site.css's off-screen
# pause already lists (as hc29's lf-w), so the pass rests while its hero is off screen.
def _num(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return (s[1:] if s.startswith("0.") else "-" + s[2:] if s.startswith("-0.") else s) or "0"
LIT = 16   # the steps of a hero's pass (here, so that Home's marks_hc30r.py, which takes _num .. _paths, has it)
def _rel(pts):
    out, px, py = [], None, None
    for x, y in pts:
        if px is None: out.append(f"M{_num(x)} {_num(y)}h0")
        else:
            dy = _num(y - py); out.append(f"m{_num(x - px)}{'' if dy.startswith('-') else ' '}{dy}h0")
        px, py = x, y
    return "".join(out)
def _paths(marks, lit=False):
    by = {}
    for x, y, k, ph, bw, bh in marks:
        by.setdefault((k, "l" if bh == 0 else "o" if bw < 0 else "b" if bw > 1 or bh > 1 else "", round(ph * LIT) if lit and ph >= 0 else -1), []).append((x, y, bw, bh))
    out = []
    for (k, kind, p), ms in sorted(by.items()):
        tone = f" k{k}" if k else ""
        on = f' pt" style="--p:{_num(p / LIT)}' if p >= 0 else ""
        if kind == "l": d = "".join(f"M{_num(x)} {_num(y)}h{_num(bw)}" for x, y, bw, bh in ms)
        elif kind == "o": d = "".join(f"M{_num(x)} {_num(y)}h{-bw - 1}v{bh - 1}h{bw + 1}z" for x, y, bw, bh in ms)
        elif kind == "b": d = "".join(f"M{_num(x)} {_num(y)}h{bw - 1}v{bh - 1}h{1 - bw}z" for x, y, bw, bh in ms)
        else:
            left = {(x, y) for x, y, _, _ in ms}
            for step, cls in ((1, "r"), (2, "r2")):
                d = []
                for horiz in (True, False):
                    for x, y in sorted(left, key=(lambda p: (p[1], p[0])) if horiz else (lambda p: (p[0], p[1]))):
                        if (x, y) not in left or x != int(x) or y != int(y): continue
                        n = 1
                        while ((x + n * step, y) if horiz else (x, y + n * step)) in left: n += 1
                        if n < 3: continue
                        for i in range(n): left.discard((x + i * step, y) if horiz else (x, y + i * step))
                        d.append(f"M{_num(x)} {_num(y)}{'h' if horiz else 'v'}{_num((n - 1) * step + 0.01)}")
                if d: out.append(f'<path class="mk{tone} {cls}{on}" d="{"".join(d)}"/>')
            if not left: continue
            kind, d = "d", _rel(sorted(left, key=lambda p: (p[1], p[0])))
        out.append(f'<path class="mk{tone} {kind}{on}" d="{d}"/>')
    return "".join(out)
def _still(fig, body, cls=""):
    """the still's root is a box of 6 x 6 cells at the lattice's corner, and the marks overflow it: a browser draws an
    svg root in its box snapped to whole px and rescales the drawing to fit, so the box must be whole px at any cell
    (6 cells are, at pixel ratios 1, 1.5, 2 and 3); the origin lies .016 of a cell in, so no mark's edge rests on half a
    pixel, where the rasterizer rounds either way (at 1440 one mark in thirty stood a pixel off its lattice)"""
    return f'<svg class="fs-still{cls}" viewBox="-.016 -.016 6 6" aria-hidden="true" focusable="false">{body}</svg>'
def note_still(fig, gid=None):
    """a formation as a still: the hero's picture, with or without JavaScript (gid: its marks in one group, which the
    margin plate draws again by reference; its path's marks in the steps of the pass), and the index's plate before
    figure.js takes it over"""
    body = _paths(FORM[fig].marks(), lit=bool(gid))
    return _still(fig, f'<g id="{gid}">{body}</g>' if gid else body)
def fg(fig, inner, pads=None):
    """the lattice's box (research.css .fg): its cells and the room its words take; the cell is a whole number of px"""
    f = FORM[fig]; p = PADS[fig] if pads is None else pads
    return f'<div class="fg" style="--w:{f.w:g};--h:{f.h:g};--pt:{_rem(p[0])};--pr:{_rem(p[1])};--pb:{_rem(p[2])};--pl:{_rem(p[3])}">{inner}</div>'
# award a4 (a4-pixel, polish): a figure whose labels are its key (note 09: the floor and its value, the 01-10 axis, and so,
# by r3's rule, the hedge label "above the floor / exact value not published") keeps that key on its still, where figure.js
# cannot set the labels (no JavaScript). Same words, sides and flags as LABELS; each at its point in the lattice's cells
KEYED = {"sessions"}
def _fl(lab, style, cls="", attrs=""):
    """one label as static markup, in figure.js's .fl grammar (research.css): the point, its rule and the words"""
    text, sub, _at, side, flags = lab[:5]
    k = _keep(flags); fl = flags.split()
    c = "".join(f" fl--{f}" for f in fl if not f.endswith("sub") and f != k)
    return f'<span class="fl{c}{cls}" data-side="{side}"{attrs} style="{style}"><span class="fl-t">{H.escape(text, quote=False)}{_small(sub, fl)}</span></span>'
def still_keys(fig, only=None):
    if fig not in KEYED: return ""
    labs = [l for l in LABELS[fig] if only is None or only(l)]
    return '<div class="fs-keys" aria-hidden="true">' + "".join(_fl(l, f"--x:{l[2][0]:g};--y:{l[2][1]:g}") for l in labs) + "</div>"
# award a4 (a4-design, medium: "the figure follows the argument"): the part of a note's drawing that a part of the note
# names. While "In this note" marks that part (research.js), the margin plate lights it: its marks stand at full strength
# while the rest of the drawing recedes, and the caption under the plate names it in the hero's words (LABELS). Only
# where the note's own text names a part the drawing has (its heading or its words); every other part of the note shows
# the whole still. Keys: the part heads, word for word (the build stops otherwise); the label LABELS names; which of the
# lattice's marks are that part (x, y, kind, ph, bw, bh). No new data and no new words
PARTS = {
    "horizon": [("The problem is horizon, not capability", "p to the power n", lambda x, y, k, ph, bw, bh: k == 0),  # "p to the n"
                ("Decomposition changes the exponent", "A gate after every step", lambda x, y, k, ph, bw, bh: y < 14 and k)],  # the gate after step k
    "weights": [("Post-training moves the rulebook into the weights", "One base model", lambda x, y, k, ph, bw, bh: k == 0),
                ("Parameter-efficient specialization and the forgetting problem", "Adapters", lambda x, y, k, ph, bw, bh: k and y < 44),
                (("Part two: proving what happened", "What must go in the record", "Replay as off-policy evaluation"), "The record", lambda x, y, k, ph, bw, bh: y >= 44)],
    "swarm": [("The verification argument", "One gate, one job each", lambda x, y, k, ph, bw, bh: x >= 50)],  # "small agents are verifiable ... at which gate"
    "boundary": [(("Why the boundary sits there", "MCP as the structural interface"), "The boundary", lambda x, y, k, ph, bw, bh: k == 2),
                 ("Idempotency as a safety property", "05–08 Execute", lambda x, y, k, ph, bw, bh: k == 1)],  # "the execution layer"
    "rulebook": [("Exceptions are the training set", "Documents, exceptions", lambda x, y, k, ph, bw, bh: x < 33 or x > 60),
                 ("Why this creates a defensible position", "The post-trained model", lambda x, y, k, ph, bw, bh: 33 <= x <= 60)],  # "a post-trained model is a moat"
    "council": [("What the council checks", "Execution Council", lambda x, y, k, ph, bw, bh: k == 0),
                ("Three operating modes", "Approved", lambda x, y, k, ph, bw, bh: k == 2 and y < 56),  # "every approved proposal"
                ("Conflict arbitration", "Proposals", lambda x, y, k, ph, bw, bh: k == 1)],  # "two decision agents propose actions"
    "ledger": [("Why append-only", "Hash of the previous record", lambda x, y, k, ph, bw, bh: k == 2 and bw == 1)],  # the links, not the newest block
    "sessions": [("The result", "Floor", lambda x, y, k, ph, bw, bh: bh == 0 and k == 0)],  # "every one above the floor we set of ten basis points": the rule
    "mastercopy": [("Phase one: prove one", "Master agent", lambda x, y, k, ph, bw, bh: k == 2),
                   ("Phase two: master and copy", "Copies", lambda x, y, k, ph, bw, bh: 30 < y < 50)],
}
def margin_plate(fig, slugs=()):
    """award a3 (a3-design, big): the margin plate beside a note's text (from 1440 px; research.css .np-rail) is the
    note's own still, drawn again at the plate's size: the hero's marks by reference (<use>: no second copy in the page),
    in whole px cells as everywhere. Each part a part of the note names (PARTS) is a second still of that part's marks
    alone, shown over the first while the note's contents mark that part (research.js; research.css .np-part), and the
    caption says its name. A keyed figure (KEYED: note 09) keeps its hedge label on the plate at all times.
    Returns (the plate, the names for its caption)"""
    f = FORM[fig]; marks = f.marks(); byname = {l[0]: l for l in LABELS[fig]}
    out, names = [_still(fig, '<use href="#fs"/>', " np-still")], []
    for heads_, name, test in PARTS.get(fig, []):
        hs = heads_ if isinstance(heads_, tuple) else (heads_,)
        for h_ in hs: assert slugify(h_) in slugs, f"PARTS[{fig!r}]: “{h_}” is not a part head of its note"
        sel = [m for m, raw in zip(marks, RAW[fig]) if test(*raw)]
        assert sel and len(sel) < len(marks), f"PARTS[{fig!r}]: “{name}” selects {len(sel)} of {len(marks)} marks"
        ss = " ".join(slugify(h_) for h_ in hs); lab = byname[name]
        out.append(_still(fig, _paths(sel), " np-part" + (" np-rule" if all(m[5] == 0 for m in sel) else "")).replace("<svg ", f'<svg data-parts="{ss}" ', 1))
        sub = lab[1] if lab[1] and "minorsub" not in lab[4].split() else None   # a value or a hedge stays with its name; a gloss does not
        names.append(f'<span class="np-name" data-parts="{ss}">{H.escape(lab[0] + (" · " + sub[0].lower() + sub[1:] if sub else ""), quote=False)}</span>')
    hedge = [l for l in LABELS[fig] if _keep(l[4])] if fig in KEYED else []
    pt = max([math.ceil(_lsize(l)[1] + 18 + 6) / 16 for l in hedge] + [0])
    return fg(fig, "".join(out) + still_keys(fig, lambda l: _keep(l[4])), (pt, 0, 0, 0)), "".join(names)
def mark_svg(fig, tones=("#F5F2EC", "#F5F2EC", "#4FCB93", "#D9675D"), quiet=".6"):
    """a formation as a file of its own (Home's three note marks, a share card): the same lattice, the tokens' values as
    presentation attributes, in cells (a mark is half a cell). Crisp where it is shown at a whole number of px a cell
    (a width that is a multiple of its viewBox's). tones: paper white, the quiet tone (drawn at `quiet`), green, red"""
    f = FORM[fig]
    def attrs(m):
        cls = m.group(1).split(); k = next((int(c[1:]) for c in cls if c[0] == "k" and c[1:].isdigit()), 0); t = cls[-1]
        a = f' stroke="{tones[k]}"' + (f' stroke-opacity="{quiet}"' if k == 1 else "")
        if t == "r": a += ' stroke-dasharray="0 1"'
        elif t == "r2": a += ' stroke-dasharray="0 2"'
        elif t == "b": a += f' fill="{tones[k]}" stroke-linejoin="miter"'
        elif t in ("l", "o"): a += ' stroke-width=".125" stroke-linecap="butt" stroke-linejoin="miter"'
        return "<path" + a
    body = re.sub(r'<path class="([^"]+)"', attrs, _paths(f.marks()))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-.25 -.25 {f.w + .5:g} {f.h + .5:g}" width="{f.w * 4 + 2:g}" height="{f.h * 4 + 2:g}">'
            f'<g fill="none" stroke-width=".5" stroke-linecap="square" shape-rendering="crispEdges">{body}</g></svg>\n')
# v2x: notes link to the instruments they describe (PAGES.md §6.4, NL-01..NL-10); targets are relative to research/
# award a3 (a3-ux): the desk is Lifecycles #desk (its own hero links there; the cut moved it off #lc01), and the act on
# the chain has one verb sitewide, "Change a record" (Home §06, Trust)
RUN = {
    "horizon": [("Watch the Council verify proposals in the swarm lab", "../index.html#lc01")],
    "weights": [("Change a record and watch the chain fail", "../index.html#governance")],
    "lifecycle": [("The lifecycle test, trait by trait", "../lifecycles.html#test")],
    "swarm": [("See the swarm by role in the swarm lab", "../platform.html#swarm")],
    "boundary": [("Explore the eight layers and the boundary", "../platform.html#architecture")],
    "rulebook": [("Find the model layer in the architecture explorer", "../platform.html#architecture")],
    "council": [("Tighten the Council in the swarm lab", "../index.html#lc01")],
    "ledger": [("Replay a ledger excerpt, then try to change the past", "../trust.html#ledger")],
    "sessions": [("See the ten sessions on the Proof page", "../evidence.html"), ("Run one simulated session on the desk", "../lifecycles.html#desk")],
    "mastercopy": [("The six lifecycle classes, status by ring", "../lifecycles.html#classes")],
}
SERIES_DISCLOSURE_RE = r"^\*Disclosures: (.+)\*$"  # the series disclosure at the end of the markdown (Post 10): one block, every note
SERIES_LD = {"@type": "CreativeWorkSeries", "@id": HOME + "research.html#series", "name": "OpenEXA Research", "url": HOME + "research.html"}

def read(p): return io.open(p, encoding="utf-8").read()
def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)

# ---------------- parse ----------------
src = read(MD)
for a, b in FIXES:
    assert src.count(a) == 1, a[:60]
    src = src.replace(a, b)
for bad in ("NASDAQ", "NYSE", "TradeStation", "Interactive Brokers"):
    assert bad not in src, bad
chunks = re.split(r"\n## Post (\d+): ", src)[1:]
posts = {}
SERIES_DISCLOSURE = None
for num, body in zip(chunks[0::2], chunks[1::2]):
    lines = body.strip().split("\n")
    title = lines[0].strip()
    rest = "\n".join(lines[1:]).strip().rstrip("-").strip()
    dek = None
    m = re.match(r"^\*(.+?)\*\s*\n", rest, re.S)
    if m: dek = m.group(1).strip(); rest = rest[m.end():].strip()
    blocks = []
    for para in re.split(r"\n\s*\n", rest):
        para = para.strip()
        if not para: continue
        if para.startswith("### "): blocks.append(("h", para[4:].strip()))
        else: blocks.append(("p", " ".join(l.strip() for l in para.split("\n"))))
    # word count and read time as published since v10 (C-122: 6 · 7 · 3 min ×8, 37 in total): counted before the move below
    words = sum(len(t.split()) for k, t in blocks if k == "p") + (len(dek.split()) if dek else 0)
    # v2x: the markdown's last post (note 02) ends on a "---" rule and the series disclosure. Neither belongs to that
    # note's body: the rule goes, and the disclosure (words verbatim) is set once per note after the body (PAGES N-07)
    if len(blocks) >= 2 and blocks[-2] == ("p", "---") and re.match(SERIES_DISCLOSURE_RE, blocks[-1][1]):
        SERIES_DISCLOSURE = re.match(SERIES_DISCLOSURE_RE, blocks[-1][1]).group(1).strip()
        blocks = blocks[:-2]
    assert ("p", "---") not in blocks, f"Post {num}: a literal '---' paragraph in the body"
    posts[int(num)] = {"num": int(num), "title": title, "dek": dek, "blocks": blocks, "words": words, "minutes": max(3, round(words / 210))}
assert sorted(posts) == list(range(1, 11)), sorted(posts)
assert SERIES_DISCLOSURE, "the series disclosure (the markdown's closing '*Disclosures: …*') was not found"

def typo(t):
    """typography only, never words (VOICE §7; lab research-editorial): the apostrophe inside a word is ’ (the notes
    carry 41 straight ones: "fund's", "isn't"); a spaced em dash keeps a no-break space before it, so it never opens a
    line. Visible text only: <title>, meta, feeds and JSON-LD keep the source characters."""
    t = re.sub(r"(?<=\w)'(?=\w)", "’", t)
    t = re.sub(r"\b(Lifecycle|Day|Phase) (\d)", r"\1" + NB + r"\2", t)  # "Lifecycle 01" never breaks across a line
    return t.replace(" — ", NB + "— ").replace(" -- ", NB + "— ")
def inline(t):
    t = H.escape(typo(t), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
    # a hyphenated compound ("hash-chained", "create-or-redeem", at most 19 letters) is never split at its hyphen across
    # two lines (research.css .nw); serif text has U+2010 by then and is left to its own balance
    return re.sub(r"(?<![\w‐-])(?=[\w-]{3,24}(?![\w-]))(\w+(?:-\w+)+)", r'<span class="nw">\1</span>', t)
def slugify(t): return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
# v2x (SYSTEM.md §2): Instrument Serif draws U+002D wide ("Post – Training"); its U+2010 is tight. Visible serif text gets
# U+2010 between letters at source (titles in <title>, meta and JSON-LD keep ASCII)
def serif(t): return re.sub(r"(?<=[A-Za-z])-(?=[A-Za-z])", "‐", t)
# r2 (system's request, r2-a11y): Instrument Serif has no U+2010 of its own, and find-in-page misses it ("Post-Training"
# on /research found nothing). The page now carries U+002D inside site.css's .hy span, whose margins take the serif's
# bearings in (site.js did this at load until now). serif() still marks the hyphens first, so inline()'s no-break rule
# leaves serif compounds alone; the mark becomes the span after escaping
HY = '<span class="hy">-</span>'
def serif_html(t): return inline(serif(t)).replace("‐", HY)
# r5 (r5-art moderate): display text never ends a line on a short function word or a clause opener ("What Ten Sessions
# on / Real Markets Taught Us", "Hash Chains as / Audit Infrastructure"): each binds to the word after it with a no-break
# space, so the line breaks before it. The words, their order and the text run are unchanged (U+00A0 searches, copies
# and reads as a space; site.js keeps it inside its word when it splits a head). Display text only (the H1, the index
# rows, the pager cards, the notes' section heads, Home's cards): <title>, meta, JSON-LD, the feed and the TOC keep plain
# spaces. Same rule as Home §07's card titles ("Why&nbsp;We&nbsp;Stopped").
BIND = "a an the of on in to for and or nor but as at by via with from is it its we our that this not how what why".split()
BIND_RE = re.compile(r"(?<![\w‐’'-])(" + "|".join(BIND) + r") (?=\S)", re.I)
# a modal keeps its "not" ("Why the execution layer / should not be a language model", never "should / not be")
AUX_RE = re.compile(r"(?<![\w‐’'-])(should|would|could|must|can|will|do|does|did|are|was|were) (?=not\b)", re.I)
def bind(t): return BIND_RE.sub(lambda m: m.group(1) + NB, AUX_RE.sub(lambda m: m.group(1) + NB, t))
def disp(t):
    """display HTML: bound (bind), serif hyphens (serif_html), and each bound run that holds a serif hyphen kept whole
    (.nw), so it never breaks at its hyphen: binding made "on·Post-" the cheapest break ("A Research Note on Post- /
    Training and Audit", r5 p1). The span holds the whole run, so site.js's split keeps it one word."""
    t = re.sub(r"[^ ]*‐[^ ]*", lambda m: "\x01" + m.group(0) + "\x02", serif(bind(t)))
    return inline(t).replace("\x01", '<span class="nw">').replace("\x02", "</span>").replace("‐", HY)
# r5 (r5-art moderate): the index's hand-set chapter heads and the ten titles break between phrases, as Home's heads do
# ("From the unit of work / to the open platform."; "Lifecycle 01. / What Ten Sessions / on Real Markets Taught Us").
# research.css sets each .ph as one unit that wraps inside itself (bound, as above) only where its column is narrower
# than it, so no zoom or text size scrolls sideways. §04's "The research contribution" is wider than its 1440 and 1024
# column, so it is bound, not phrased ("The research / contribution / is four constants.").
def PH(*parts): return " ".join(f'<span class="ph">{disp(p)}</span>' for p in parts)
# The titles' phrases, part by part (a title's head, its sentence, a research note's "A Research Note on …"): " | " marks
# where a line may break. The build stops unless every entry is part of a title, word for word.
PHRASES = [
    "Compounding Error | and the Case for Decomposition.", "A Research Note | on Agent Architecture",
    "Specializing a Model | to a Rulebook | and Proving What It Did.", "A Research Note | on Post-Training and Audit",
    "Why We Stopped | Building Assistants", "Why Five Thousand Small Agents | Beat One Large One",
    "The One Boundary | That Matters", "Post-Training a Model | on a Rulebook, | Not on the Internet",
    "Governance | in Milliseconds", "Hash Chains | as Audit Infrastructure",
    "What Ten Sessions | on Real Markets | Taught Us", "How a Proven Agent | Becomes a Platform",
]
PHRASED = {p.replace(" | ", " "): p.split(" | ") for p in PHRASES}
for _p in PHRASED: assert any(_p in p["title"] for p in posts.values()), f"PHRASES: “{_p}” is not part of a title, word for word"
def phrased(part): return PH(*PHRASED[part]) if part in PHRASED else disp(part)
def us(t):  # US spelling in site-written copy (VOICE §6.3); the blog collection ledes come from build_blog.py's summary
    return typo(re.sub(r"\blabour\b", "labor", re.sub(r"\bbehaviour\b", "behavior", t)))
def kind(post):  # one number per row (PAGES E-5): the reading-order number is the row's; the kind is said in words
    return "Research note" if post["label"] == "Research note" else f"Series, part {int(post['label'].split('·')[1])} of 8"
def title_html(t):
    """an authored title, words and capitals kept (E-4): the two research notes' 'A Research Note on …' is set as the
    title's second line, smaller, so no title runs past three lines"""
    m = re.match(r"^(.+?\.) (A Research Note on .+)$", t)
    if m: return f'{phrased(m.group(1))} <span class="title-sub">{phrased(m.group(2))}</span>'
    # lab research-editorial: a series title is a short head and a longer sentence ("Lifecycle 01. What Ten Sessions
    # on Real Markets Taught Us"). Each part is its own span, so a line can break at the sense break, never inside
    # "Lifecycle 01. What" (research.css decides where the break is taken); the words and the text run are unchanged
    # r5: inside each part, the line breaks between its phrases (PHRASES; bound, disp())
    m = re.match(r"^(.+\.) ([A-Z].+)$", t)
    return f'<span class="t-head">{disp(m.group(1))}</span> <span class="t-rest">{phrased(m.group(2))}</span>' if m else phrased(t)
def cap_html(fig, cls="figcap", title=False, attrs=""):
    """cut (1 Nov): beside a drawing, its hedge; the index's strip also has the line that says what is drawn (phones only,
    where the labels do not fit; research.js writes it from the row)"""
    t, h = CAPTIONS[fig]
    tt = '<span class="figcap-t"></span>' if title else ""
    return f'<p class="{cls}"{attrs}>{tt}<span class="figcap-h">{H.escape(h, quote=False)}</span></p>'

# ---------------- templates from the live homepage ----------------
index_html = read(os.path.join(ROOT, "index.html"))
NAV = re.search(r'  <header class="nav">.*?</header>\n  <div class="nav-menu">.*?\n  </div>\n', index_html, re.S).group(0)
FOOTER = re.search(r'  <footer class="footer">.*?</footer>\n', index_html, re.S).group(0)
# the Lifecycle 01 sessions: ONE record (#oxa-sessions, on the home and Proof pages) that the chart and every session count
# are drawn from. The 'sessions' figure (note 09) draws ten columns for ten sessions: a record with another count needs
# that figure and the note looked at, so the build stops. Hill climb hc7: the figure no longer colours a column by its
# NAV regime (Proof's step line says that), so the note's stage carries no regimes (was data-regimes, since r1)
SESSIONS = json.loads(re.search(r'<script type="application/json" id="oxa-sessions">(.*?)</script>', index_html, re.S).group(1))["sessions"]
assert len(SESSIONS) == 10, f"#oxa-sessions: note 09's figure draws ten sessions; the record gives {len(SESSIONS)}"
HEAD_LINKS = '''  <link rel="apple-touch-icon" href="{p}assets/img/apple-touch-icon.png">
  <link rel="manifest" href="{p}site.webmanifest">
  <link rel="icon" type="image/svg+xml" href="{p}assets/img/favicon.svg">
  <link rel="preload" href="{p}assets/fonts/instrument-serif-400-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{p}assets/fonts/inter-var-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{p}assets/css/site.css">
  <link rel="stylesheet" href="{p}assets/css/research.css">'''
ARROW = '<svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" focusable="false"><path d="M2 8h11M9 4l4 4-4 4"/></svg>'
OUTB = '<svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" focusable="false"><path d="M5 11L11 5M6 5h5v5"/></svg>'
SCHOLAR = "https://scholar.google.com/citations?user=P40aOHIAAAAJ"
BLOG = json.load(open(os.path.join(str(DATA), "blog_summary.json"), encoding="utf-8"))  # written by build_blog.py

# award budgets (the a4 jury's two big items, index and notes): the pages' three scripts start after the first paint, as
# Lifecycles' and Trust's do (system's afterpaint.js: site.js at the paint, then figure.js and research.js in that order).
# They were three defer tags, which run before the text's paint is counted: Lighthouse's simulated FCP and LCP took in
# their download and their evaluation at 4x (mobile 97, 98-99 before the award pass). Without JavaScript nothing changes;
# with it, the page paints from its HTML and CSS (the hero's still, the words), and the drawing starts as it did, a moment
# later. Shared-engine tags are chrome: system signs this off (CHANGE_REQUESTS, award budgets)
AFTER_PAINT = ("assets/js/figure.js", "assets/js/site.js", "assets/js/research.js")
def after_paint(prefix):
    return f'  <script src="{prefix}assets/js/afterpaint.js" defer data-after-paint="{" ".join(prefix + s for s in AFTER_PAINT)}"></script>'

def chrome(prefix, current):
    nav = NAV.replace('href="', f'href="{prefix}').replace(f'href="{prefix}#', 'href="#')
    nav = nav.replace(f'<a href="{prefix}research.html">Research</a>', f'<a href="{prefix}research.html" aria-current="page">Research</a>') if current == "research" else nav
    foot = FOOTER.replace('href="', f'href="{prefix}').replace(f'href="{prefix}http', 'href="http').replace(f'href="{prefix}mailto', 'href="mailto')
    return nav, foot

# award a1 (system's request, a1-dev): the share card's alt text says what the card shows (the page's H1, then the globe the
# research cards carry), as launch_meta_v9.py writes it for the top pages, plus twitter:image:alt and og:locale
# award a2 (system's request): build_og.py now gives each note's card the note's own still (svg.fs-still) in place of the
# globe, and the index's card its library still; the index's alt is launch_meta_v9.py's STILL_PIC, word for word, so the
# head this build writes is the head the chain leaves
CARD_ALT = " Beside it, the note’s figure, drawn as a still."
INDEX_CARD_ALT = " Beside it, the page’s open book: ten engraved leaves, one for each note."  # hc29 (HC29 12): the engraved book, its card re-rendered
def og(prefix, url, title, desc, h1=None, pic=CARD_ALT, links=""):
    alt = (h1 or title).rstrip(); alt = (alt if alt[-1] in ".!?" else alt + ".") + pic  # a title without its own stop gets one
    return f'''  <meta name="description" content="{H.escape(desc, quote=True)}">
  <meta name="theme-color" content="#0E1512">
  <link rel="canonical" href="{url}">
{links}  <meta property="og:url" content="{url}">
  <meta property="og:site_name" content="OpenEXA">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{H.escape(title, quote=True)}">
  <meta property="og:description" content="{H.escape(desc, quote=True)}">
  <meta property="og:image" content="{og_image(url)}">
  <meta property="og:image:alt" content="{H.escape(alt, quote=True)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:locale" content="en_US">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{H.escape(title, quote=True)}">
  <meta name="twitter:description" content="{H.escape(desc, quote=True)}">
  <meta name="twitter:image" content="{og_image(url)}">
  <meta name="twitter:image:alt" content="{H.escape(alt, quote=True)}">
  {ROBOTS}
  {FEED_LINKS[0]}
  {FEED_LINKS[1]}
{HEAD_LINKS.format(p=prefix)}'''

# ---------------- articles ----------------
ordered = [posts[n] for n in ORDER]
for i, post in enumerate(ordered):
    slug, fig, label, dek_short = META[post["num"]]
    post.update({"slug": slug, "fig": fig, "label": label, "short": dek_short, "order": i + 1, "file": f"research/{i + 1:02d}-{slug}.html"})

# cut (1 Nov): a pager card is where it leads and the title there; the summaries under the titles are gone
def pager_card(p, k, cls=""):
    return f"<a class='pager-card{cls}' href='{os.path.basename(p['file'])}'><span class='k'>{k}</span><h3>{title_html(p['title'])}</h3></a>"

for i, post in enumerate(ordered):
    prev = ordered[i - 1] if i else None
    nxt = ordered[i + 1] if i + 1 < len(ordered) else None
    nav, foot = chrome("../", "research")
    heads = [(slugify(t), t) for k, t in post["blocks"] if k == "h"]
    # the link is a grid (numeral, words): the words are one span, so a no-break compound inside them is not a grid item
    toc = "".join(f'<li><a href="#{a}"><span>{inline(t)}</span></a></li>' for a, t in heads)
    body = []
    # cut (1 Nov): the hero is the title and the drawing. A research note's standfirst (the markdown's italic line, the
    # author's own words) opens the body instead of standing as a 40-word lede under the title; the series notes'
    # site-written summary (META) is no longer printed on the page (it stays the share and search description)
    if post["dek"]: body.append(f'<p class="dek">{inline(post["dek"])}</p>')
    first_p = True
    for k, t in post["blocks"]:
        if k == "h": body.append(f'<h2 id="{slugify(t)}">{disp(t)}</h2>')  # r5: bound as the titles are (disp)
        else:
            body.append(f'<p{" class=\"lead\"" if first_p else ""}>{inline(t)}</p>'); first_p = False
    dek = post["dek"] or post["short"]
    # award a2 (a2-dev): a search result shows ~160 characters; notes 01 and 02 described themselves with the author's
    # standfirst (295 and 251), cut mid-sentence. Their meta, share and card description is now the note's own one-line
    # summary (META, as on Home's cards and in the feed); the standfirst still opens the body and stays the schema's
    meta_desc = dek if len(dek) <= 160 else post["short"]
    title = post["title"]
    url = f"https://www.openexa.com/{post['file']}"
    n = f"{post['order']:02d}"
    run = "".join(f'<li><a class="link-arrow" href="{href}">{H.escape(text, quote=False)}{NB}{ARROW}</a></li>' for text, href in RUN[post["fig"]])
    # award a4 (a4-dev, polish): the ten notes are one series for crawlers too, as the blog's series is: rel prev / next in
    # the reading order 01-10 (isPartOf is already the CreativeWorkSeries, with its position)
    rel_links = "".join(f'  <link rel="{r}" href="{HOME}{q["file"]}">\n' for r, q in (("prev", prev), ("next", nxt)) if q)
    long_title = len(re.sub(r" A Research Note on .+$", "", title)) > 52
    # hc26r (RES-1, SYS-2 "the drawing travels"): the hero's figure is the page's one data-vt-dest (site.css names it
    # `fig`), so the drawing a link carries (the index's plate, Home §05's marks) becomes it over the page turn. Its still
    # is whole at the first paint, so it lands drawn. The pager carries no drawing, so it has no source (notes/research.md)
    # hc30r: the stage follows the words in the page (it is placed, not flowed), so the hedge it now holds is read after
    # the title; the drawing and its labels are hidden from assistive technology one by one, the hedge is not. The hero
    # has no canvas: its still is the figure, and the pass of light is the still's own (LIT, above)
    plate = margin_plate(post["fig"], {a for a, _ in heads})
    first = "<a class='pager-card' href='../research.html'><span class='k'>← Research</span><h3>All ten notes</h3></a>"
    last = "<a class='pager-card next' href='../access.html'><span class='k'>Next →</span><h3>Bring us a lifecycle.</h3></a>"
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{H.escape(title)} — OpenEXA Research</title>
{og("../", url, title + " — OpenEXA Research", meta_desc, title, links=rel_links)}
  {ld({"@type": "TechArticle", "@id": url + "#article", "headline": title, "description": dek, "url": url, "mainEntityOfPage": url,
        "datePublished": PUBLISHED, "inLanguage": "en", "image": [og_image(url)], "author": ORG, "publisher": ORG,
        "isPartOf": SERIES_LD, "position": post["order"], "wordCount": post["words"], "timeRequired": f"PT{post['minutes']}M"},
       crumbs(("Research", HOME + "research.html"), (title, url)))}
</head>
<body data-page="note" data-nav="dark-start" class="article-page">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain article-hero">
      <div class="container">
        <div class="article-hero-grid">
          <div>
            <h1 class="display-1 article-title{' article-title--long' if long_title else ''}{' article-title--split' if 't-head' in title_html(title) else ''}" data-reveal data-split>{title_html(title)}</h1>
            <div class="article-meta" data-reveal style="--d:120ms"><span>Founder’s notes</span><span>{post['minutes']}{NB}min read</span></div>
          </div>
        </div>
      </div>
      <div class="figure-stage article-figure has-still" data-figure="{post['fig']}" data-vt-dest>{fg(post['fig'], note_still(post['fig'], "fs") + still_keys(post['fig']) + cap_html(post['fig'], "figcap article-figcap"))}{labels_html(post['fig'])}</div>
    </section>

    <section class="section article-body-section">
      <div class="container">
        <div class="grid">
          <nav class="col-3 article-side" aria-label="In this note">
            <div class="sticky">
              <ol class="toc" data-toc>{toc}</ol>
            </div>
          </nav>
          <article class="col-7 offset-5 article">
            {"".join(body)}
            <div class="article-end"><span class="mark" aria-hidden="true"></span></div>
            <div class="note-run"><ul>{run}</ul></div>
            <div class="note-disc"><p>{H.escape(SERIES_DISCLOSURE, quote=False)} <a href="#disclosures">See the disclosures.</a></p></div>
          </article>
          <div class="np-rail" aria-hidden="true"><figure class="np-plate"><div class="np-stage is-dark">{plate[0]}</div><figcaption>{cap_html(post['fig'], "figcap np-cap").replace("</p>", f'<span class="np-names">{plate[1]}</span></p>')}</figcaption></figure></div>
        </div>
      </div>
    </section>

    <section class="section is-paper-2 section--tight">
      <div class="container">
        <div class="pager">
          {pager_card(prev, "← Previous") if prev else first}
          {pager_card(nxt, "Next →", " next") if nxt else last}
        </div>
      </div>
    </section>
  </main>

{foot}
{after_paint("../")}
</body>
</html>
'''
    write(os.path.join(ROOT, post["file"].replace("/", os.sep)), page)
    print("wrote", post["file"], f"({post['minutes']} min)")

# ---------------- index ----------------
nav, foot = chrome("", "research")
rows = []
# cut (1 Nov): a row is the note's number, its title and its read time; the summaries under the titles are gone (the
# plate beside the list shows each note's idea). The row carries the plate's words for that note: what is drawn (the
# phone strip) and the hedge; hc23: the strip's shorter line (STRIP). hc26r (RES-1): each row's link names the plate
# (data-vt-src, the figure-stage's id) as the drawing that travels into the note's hero; research.js keeps it off a row
# whose figure the plate has not turned to yet
for post in ordered:
    t, h = CAPTIONS[post["fig"]]
    cap = " ".join(f'data-cap-{k}="{H.escape(v, quote=True)}"' for k, v in (("t", t), ("s", STRIP[post["fig"]]), ("h", h)) if v)
    rows.append(f'''          <li class="post" data-figure-target="{post['fig']}" data-figure-stage="research-figure" {cap}>
            <a href="{post['file']}" data-vt-src="research-figure">
              <span class="post-n">{post['order']:02d}</span>
              <div class="post-main">
                <h3>{title_html(post['title'])}</h3>
              </div>
              <div class="post-meta"><span>{post['minutes']}{NB}min</span>{ARROW}</div>
            </a>
          </li>''')
notes = [p for p in ordered if p["label"] == "Research note"]
url = "https://www.openexa.com/research.html"
# r2: the share title is the <title>, as launch_meta_v9.py writes it, so research.html no longer differs between the
# research build and the chain's last step (r1 open issue: built alone it said "Research — OpenEXA")
INDEX_TITLE = "Research — OpenEXA · The thinking behind agentic lifecycles"
# award a2 (a2-dev, polish): 159 characters, not 220 (search results cut at ~160); the same topics in the same words
desc = "Ten notes on swarm-based agentic lifecycles: compounding error, post-training, the Execution Council, the hash-chained ledger and ten sessions on real capital."
assert len(desc) <= 160, len(desc)
# cut (1 Nov): the blog's three collections as three titles with their size and years; each row is the link.
# award a2 (a2-design, polish: "three tall ruled cells hold only a title and a count; the row reads empty at every
# width"): the section is a spread, as Trust's "What the agents do not do." and Platform's roles: the heading on the
# left, the three collections as ruled rows on the right, each title with its count and years on one baseline, as the
# notes' rows above (title, read time, arrow), then the two links. A list of three links, not three cards
def years(c): return str(c["years"][0]) if c["years"][0] == c["years"][1] else f'{c["years"][0]}–{c["years"][1]}'
collections = "\n".join(f'              <li><a href="blog/index.html#{c["key"]}"><h3>{H.escape(c["label"])}</h3><span class="rs-coll-m"><span>{c["count"]}{NB}posts · {years(c)}</span>{ARROW}</span></a></li>' for c in BLOG['collections'])
BOOK = library_svg()
index_page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{INDEX_TITLE}</title>
{og("", url, INDEX_TITLE, desc, "The thinking behind the swarm.", INDEX_CARD_ALT).replace('content="article"', 'content="website"')}
  {ld({"@type": "CollectionPage", "@id": url + "#webpage", "url": url, "name": "Research — OpenEXA", "description": desc,
       "isPartOf": WEBSITE, "primaryImageOfPage": og_image(url), "inLanguage": "en",
       "mainEntity": {"@type": "ItemList", "itemListElement": [
           {"@type": "ListItem", "position": p["order"], "url": HOME + p["file"], "name": p["title"]} for p in ordered]}},
      crumbs(("Research", url)), id="ld-research")}
</head>
<body data-page="research" data-nav="dark-start" class="research-page">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain research-hero" style="--bk-r:{BOOK[2]}">
      <div class="figure-stage research-figure" id="research-library" aria-hidden="true"><div class="rs-bk">{BOOK[0]}{BOOK[1]}</div></div>
      <div class="container">
        <div class="grid">
          <div class="col-7">
            <h1 class="display-1" data-reveal data-split>The thinking behind the swarm.</h1>
            <p class="lede mt-3" data-reveal style="--d:120ms">Ten notes on why high-stakes work should be run by thousands of narrow agents behind one deterministic boundary.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- v2x: the shelf. The ten notes, and beside them (pinned below them on phones) one plate that shows the figure of
         the note pointed at, focused or, on touch screens, read: research.js. Without JavaScript the plate is not drawn
         and the list takes the full width (research.css, @media (scripting: none)). Cut (1 Nov): no chapter heads; the
         two research notes and the eight-part series read as one contents page, a wider gap between 02 and 03 -->
    <div class="rs-shelf">
      <section class="section" id="notes" data-chapter="Research notes" data-chapter-short="Notes" data-n="01">
        <div class="container">
          <div class="rs-col">
            <h2 class="sr-only">Research notes</h2>
            <ol class="posts-list" data-reveal>
{chr(10).join(rows[:2])}
            </ol>
          </div>
        </div>
      </section>

      <section class="section" id="series" data-chapter="The series" data-n="02">
        <div class="container">
          <div class="rs-col">
            <h2 class="sr-only">The series</h2>
            <ol class="posts-list" data-reveal start="3">
{chr(10).join(rows[2:])}
            </ol>
          </div>
        </div>
      </section>

      <div class="rs-rail" aria-hidden="true">
        <div class="container rs-rail-in">
          <figure class="rs-plate">
            <div class="rs-stage is-dark grain"><div class="figure-stage" id="research-figure" data-figure="{ordered[0]['fig']}">{fg(ordered[0]['fig'], note_still(ordered[0]['fig']))}<canvas></canvas>{"".join(labels_html(p['fig'], pad=True) for p in ordered)}</div></div>
            <figcaption class="rs-caption">{cap_html(ordered[0]['fig'], 'figcap rs-cap', title=True)}</figcaption>
          </figure>
        </div>
      </div>
    </div>

    <section class="section is-paper-2" id="blog" data-chapter="The blog" data-n="03">
      <div class="container">
        <div class="grid rs-blog">
          <h2 class="display-2 col-6" data-reveal data-split>{PH("Three collections,", "from market structure", "to AI agents.")}</h2>
          <div class="col-6 rs-blog-side">
            <ul class="rs-coll" data-reveal style="--d:80ms">
{collections}
            </ul>
            <div class="row-links" data-reveal style="--d:140ms"><a class="link-arrow" href="blog/index.html">All {BLOG['total']} posts {ARROW}</a><a class="link-arrow scholar-link" href="{SCHOLAR}" target="_blank" rel="noopener">The papers on Google Scholar {OUTB}</a></div>
          </div>
        </div>
      </div>
    </section>

    <section class="cta-band is-dark grain">
      <div class="container">
        <h2 class="display-2" data-reveal data-split>Three of these ideas run in your browser.</h2>
        <div class="row" data-reveal style="--d:120ms">
          <a class="btn" href="index.html#lc01">Open the swarm lab {ARROW}</a>
          <a class="btn btn--ghost" href="index.html#governance">Change a record</a>
          <a class="btn btn--ghost" href="lifecycles.html#desk">Run the desk</a>
        </div>
      </div>
    </section>
  </main>

{foot}
{after_paint("")}
</body>
</html>
'''
write(os.path.join(ROOT, "research.html"), index_page)
print("wrote research.html")
atom(os.path.join(OUT_DIR, "feed.xml"), "OpenEXA Research", "Research notes and the series behind OpenEXA's agentic infrastructure.",
     url, [{"url": HOME + p["file"], "title": p["title"], "published": PUBLISHED, "updated": PUBLISHED, "author": "OpenEXA",
            "summary": p["short"]} for p in ordered])
print("wrote research/feed.xml")

# homepage teaser cards (three featured) → written for the caller to insert, in Home §07's own form (home r1): the kind
# as kind() says it, the research notes' "A Research Note on …" as the title's second line, and Home's .nowrap (the
# research pages' .nw is scoped to them)
featured = [ordered[0], ordered[1], ordered[2]]
def card_title(t):
    m = re.match(r"^(.+?\.) (A Research Note on .+)$", t)
    sh = lambda s: disp(s).replace('class="nw"', 'class="nowrap"')  # r5: bound as on Research (disp; site.css's .nowrap)
    return f'{sh(m.group(1))} <span class="title-sub">{sh(m.group(2))}</span>' if m else sh(t)
cards = "\n".join(f'''          <a class="card research-card" href="{p['file']}"><div class="n"><span>{p['order']:02d}</span><span>{H.escape(kind(p))}</span></div><h3 class="h4">{card_title(p['title'])}</h3><p>{inline(p['short']).replace('class="nw"', 'class="nowrap"')}</p><span class="link-arrow mt-3">{p['minutes']} min read {ARROW}</span></a>''' for p in featured)
write(os.path.join(os.path.dirname(os.path.abspath(__file__)), "research_cards.html"), cards)
print("featured cards written")
