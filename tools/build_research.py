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
    # note 09: the colours are the record's (data-regimes, from #oxa-sessions); the floor line is not a scale. Cut (1 Nov):
    # each column fills to the floor and shows ONE open unit above it (figure.js), never a scatter; the label "above the
    # floor / exact value not published" stays beside it
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
# award a2 gave note 09 a colour key ("Green: premium · white: discount"): each session was drawn in its NAV regime's
# colour. Hill climb hc7 (director item 8): Home and Proof draw the same ten sessions as ten green columns, the regime
# a step line below them, and white columns read as failed sessions there. Note 09 now draws them as Proof does (every
# column green to the floor, the open unit above it a khaki outline), so it needs no key: KEYS and its slot are gone
# v2x lab (research moment): every figure is read as a plate. Its labels pin to points of the formation (figure.js, a
# stage with data-plate projects data-at, the formation's own x,y,z, onto the screen each frame) and say what each part
# is, in the words of its caption or its note: no new fact, no number the caption does not already state. Points are
# figure.js's geometry (FORMS): a formation that moves needs its labels moved here. Sides: r, l (text beside the point,
# its first line on the rule), t, b (centred above, below), tl, tr, bl, br (above or below, text ending or starting at
# the point). Flags: "minor" (dropped on a small stage), "minorsub" (its second line, a gloss, dropped on a small stage;
# never for a hedge), "acc" (the green part), "rej" (a rejection: the only red text), "n" (a numeral alone, as note 09's
# axis: mono, as a paper plate's .hp-lab--n), "nsub" (its second line a value, "10 bps": mono). Hill climb hc3 (director
# item 2): the words are the paper plates' caption register (research.css .fl-t: Inter, sentence case; numerals in a
# phrase stay in it, tabular, as Platform's "Above · 01–04"). An optional last item (r1) is where
# the words begin when the point lies inside the drawing: the rule reaches out to it (figure.js data-to, --lead).
# Path: the span of the formation's own path (FORMS' fifth value, 0..1) the label names; while the pulse walks the
# path it lights each label it passes, so the plate reads itself out in the note's order. None: the part is not on
# the path (it is named, never lit).
# r3 (r3-a11y moderate): "keep" marks a label that carries a hedge (note 09 "exact value not published", note 10 "phase
# two, on the roadmap"). It is listed first, so where words would cross, the claim-side label yields to it; where its
# own side has no room (a phone's stage), figure.js looks for another free slot round its point; and if there is none,
# the plate shows no labels at all, so a drawing never names its parts without their hedge (data-keep). "keep=t,tl,tr"
# limits the slots to those sides: "above the floor" never stands below the columns it describes.
def _cols():  # note 09: ten columns, x = -1.08 + c * 0.24 (figure.js sessions), numbered in the record's order
    # award a1 (a1-pixel, D5): the numbers are the drawing's axis, read as one row (figure.js sets them on one baseline),
    # at one weight and one dot size: the pulse no longer lights them one by one (a still showed a row that faded from
    # left to right); it still runs through the columns themselves
    return [(f"{c + 1:02d}", None, (round(-1.08 + c * 0.24, 2), -0.78, 0), "b", "n" if c in (0, 9) else "minor n", None)
            for c in range(10)]
def _loop(n):  # note 03: node n of figure.js lifecycle (a ring of r 0.95, tilted 0.9, from angle 0.5)
    a = n / 6 * math.tau + 0.5; x, z = math.cos(a) * 0.95, math.sin(a) * 0.95
    return (round(x, 3), round(z * math.sin(0.9) * 0.5, 3), round(z * math.cos(0.9), 3))
LABELS = {
    "horizon": [("Verification gate", None, (-0.69, -0.74, 0.14), "b", "", (0.2, 0.2)),
                ("A gate after every step", None, (0.72, 0.57, 0.14), "t", "acc", (0.81, 0.81)),
                ("p to the power n", None, (0.92, -0.55, -0.12), "b", "", (0.9, 0.9))],  # p, the note's variable, keeps its case
    "weights": [("One base model", None, (-0.46, 0.22, 0), "l", "", None, (-0.84, 0.22, 0)),
                ("Adapters", None, (0.705, 0.363, 0), "r", "", (0.0, 0.5)),
                ("The record", "Each holds the previous hash", (0.14, -0.74, 0), "r", "minorsub", (0.55, 0.95))],
    # the note's own definition of a lifecycle, in its order round the loop. hc3: Inter's taller line beside a node lay on
    # the ring's arc (figure.js hid "Record" at 1440 and 3840, "Decisions, approvals" on the index's plate), so the two
    # side labels' words begin just past the ring's edge, the rule reaching out to them
    "lifecycle": [("Signal", None, _loop(0), "r", "", (0.0, 0.03)),
                  ("Decisions, approvals", None, _loop(2), "l", "", (0.18, 0.56), (-1.04,) + _loop(2)[1:]),
                  ("Executes against an external counterparty", None, _loop(4), "b", "minor", (0.74, 0.74)),
                  ("Record", None, _loop(5), "r", "acc", (0.93, 0.93), (1.04,) + _loop(5)[1:])],
    "swarm": [("One large agent", None, (-0.72, 0.45, 0), "t", "", None),
              ("One gate, one job each", None, (0.64, 0.46, 0), "t", "acc", None)],
    "boundary": [("01–04 Decide", None, (-0.8, 0.4, 0.36), "l", "", (0.0, 0.34)),
                 ("The boundary", None, (-0.92, 0, 0.46), "l", "acc", (0.44, 0.44)),
                 ("05–08 Execute", "Deterministic code", (-0.8, -0.4, 0.36), "l", "minorsub", (0.55, 0.89))],
    "rulebook": [("Documents, exceptions", None, (1.05, -0.47, 0), "b", "", (0.08, 0.2)),
                 ("The post-trained model", None, (0, 0.52, 0), "t", "", (0.96, 0.96))],
    "council": [("Proposals", None, (0.02, 0.95, 0), "r", "", (0.0, 0.1)),
                ("Execution Council", None, (-0.34, 0.1, 0), "l", "", (0.42, 0.42)),
                ("Approved", None, (0, -0.86, 0), "l", "acc", (0.84, 0.92)),
                ("Rejected, logged", None, (1.15, -0.5, 0), "b", "rej", (0.9, 0.9))],
    "ledger": [("Record 01", None, (-1.0, 0.63, 0), "t", "", (0.0, 0.06)),
               # hc3: on the link between records 02 and 03 (the margin plate's point since a4), its words beside the next
               # record, the rule reaching out past it (on phones figure.js sets them above, "tr"): at the chain's middle
               # figure.js hid them on every desktop since r1, the words lying on the blocks
               ("Hash of the previous record", None, (-0.571, 0.314, 0.156), "r", "", (0.17, 0.21), (-0.27, 0.314, 0.156)),
               ("Newest", None, (1.0, -0.63, 0), "b", "acc", (0.875, 0.9))],
    # the floor is read like an axis, named at the line's left end, the first line on the rule. Award a3 (a3-design): the
    # site's one order for it, the word then its value ("Floor" over "10 bps", as Proof's Fig. 1.1 and Home's overture,
    # which since hc3 also set the word in Inter and the value in mono)
    # r3: each hedge label first ("keep", below). Cut (1 Nov): "Above the floor" points at the top of the one open unit
    # each column carries (figure.js sessions: the floor F = 0.48, the open unit up to 0.625)
    "sessions": [("Above the floor", "Exact value not published", (0, 0.615, 0), "t", "keep=t,tl,tr", None),   # hc29: the open block's top is 0.588
                 ("Floor", "10\u00a0bps", (-1.25, 0.48, 0.07), "l", "nsub", None),
                 # hc29 (the director's HC29 item 2, for research): the columns stand on a 0 baseline, as on Proof's Fig. 1.1
                 # (its "0" in mono at the rule's left end), and no longer hang from the floor
                 ("0", None, (-1.25, -0.72, 0.07), "l", "n", None)] + _cols(),
    "mastercopy": [("Copies", "Phase two, on the roadmap", (0.93, -0.18, -0.07), "tl", "keep", (0.74, 0.74)),
                   ("Master agent", None, (0.31, 0.62, 0), "r", "acc", (0.0, 0.06)),
                   ("One control plane", None, (-1.3, -0.77, 0), "br", "", (0.9, 0.9))],
}
# award a2 (a2-pixel, medium): a plate's rules, drawn as lines over its points in the labels' space (figure.js .fl-line:
# both ends projected each frame, so the line sways with the drawing and rests level, on whole pixels). Note 09's 10 bps
# floor was 1,200 khaki points, a 6-8 px soft band at 1:1, while Proof draws the same floor as a crisp rule; it is now
# one hairline (--stroke), from end to end of where those points lay. It is part of the drawing, not a label: it shows
# whenever the plate's words could not (a phone's strip, a hedge with no room)
RULES = {"sessions": [((-1.25, 0.48, 0.07), (1.25, 0.48, 0.07)), ((-1.25, -0.72, 0.07), (1.25, -0.72, 0.07))]}
# hc29: which of a figure's rules is its 0 baseline (the axis: drawn quieter than the floor, the data's own line, and never lit)
BASE = {"sessions": {1}}
def _base(fig, i): return " is-0" if i in BASE.get(fig, ()) else ""
def _keep(flags): return next((f for f in flags.split() if f.split("=")[0] == "keep"), None)
def _small(sub, fl):
    """a label's second line: a gloss (minorsub: dropped on a small stage) or a value (nsub: mono, as .hp-lab--n)"""
    if not sub: return ""
    c = ' class="fl-minor"' if "minorsub" in fl else ' class="fl-v"' if "nsub" in fl else ""
    return f"<small{c}>{H.escape(sub, quote=False)}</small>"
assert all(not _keep(l[4]) for ls in LABELS.values() for l in ls[1:]), "a hedge label (keep) is listed first"
def labels_html(fig):
    out = [f'<span class="fl-line{_base(fig, i)}" data-at="{a[0]:g},{a[1]:g},{a[2]:g}" data-line="{b[0]:g},{b[1]:g},{b[2]:g}"></span>' for i, (a, b) in enumerate(RULES.get(fig, []))]
    for i, (text, sub, (x, y, z), side, flags, path, *to) in enumerate(LABELS[fig]):
        k = _keep(flags)
        cls = "".join(f" fl--{f}" for f in flags.split() if not f.endswith("sub") and f != k)
        keep = (f' data-keep="{k.partition("=")[2].replace(",", " ")}"' if "=" in k else " data-keep") if k else ""
        small = _small(sub, flags.split())
        ph = f' data-ph="{path[0]:g},{path[1]:g}"' if path else ""
        reach = f' data-to="{to[0][0]:g},{to[0][1]:g},{to[0][2]:g}"' if to else ""
        out.append(f'<span class="fl{cls}" data-at="{x:g},{y:g},{z:g}"{reach} data-side="{side}"{ph}{keep} style="--i:{i}"><span class="fl-t">{H.escape(text, quote=False)}{small}</span></span>')
    return f'<template data-labels><div class="fig-labels" data-for="{fig}">{"".join(out)}</div></template>'
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
# award a1 (a1-dev, polish): every note's hero carries its formation as a still in the page, as the index's library has
# since r2: without JavaScript or WebGL the hero's right half was empty, and with them the drawing arrived only after
# figure.js started. FORMS below is figure.js's FORMS ported line for line, with its random generator (the same LCG, the
# same seeds, the same order of draws), so the still's dots are the points the plate draws, seen by the same camera in
# the pose it rests in (face-on; eye 0, 0.35, 4.4; fov 0.62; --figure-scale .84 x figure.js FIT). Every K-th point that
# is not dust, as a zero-length stroke with round caps (a dot), one path per colour and depth step. research.css sizes
# it as the stage sizes the points (.fs-still) and fades it out under them once they are drawn. A change to a formation
# in figure.js needs the same change here (the build cannot see it): the still would then disagree with the plate.
TAU = 2 * math.pi
def _rng(seed):
    s = [seed & 0xFFFFFFFF]
    def r():
        s[0] = (s[0] * 1664525 + 1013904223) & 0xFFFFFFFF
        return s[0] / 4294967296
    return r
def _n(x): return math.ceil(x)  # JS "for (i = 0; i < x; i++)": ceil(x) passes for x > 0
def _forms(name, N, rnd, g):
    P = []; push = P.append
    if name == "horizon":
        floorN, curveN, stairN = math.floor(N * 0.18), math.floor(N * 0.30), math.floor(N * 0.34)
        for i in range(floorN): push([(rnd() * 2 - 1) * 1.25, -0.72 + g() * 0.004, (rnd() * 2 - 1) * 0.5, 7])
        for i in range(curveN):
            t = rnd(); y = -0.72 + 1.3 * math.pow(0.986, t * 160); push([-1.15 + t * 2.3, y + g() * 0.02, (rnd() - 0.5) * 0.08 - 0.12, 0])
        for i in range(stairN):
            t = rnd(); step = math.floor(t * 10); y = 0.52 - (step % 2) * 0.05 + g() * 0.012; push([-1.15 + t * 2.3, y, (rnd() - 0.5) * 0.08 + 0.14, 2])
        gateN = math.floor(N * 0.011)
        for s in range(11):
            x = -1.15 + s * 0.23
            for i in range(gateN): push([x + g() * 0.004, -0.72 + rnd() * 1.26, 0.14 + g() * 0.01, 1])
    elif name == "weights":
        sph = math.floor(N * 0.42)
        for i in range(sph):
            la = math.asin(rnd() * 2 - 1); lo = rnd() * TAU; r = 0.46 * math.pow(rnd(), 0.25)
            push([r * math.cos(la) * math.sin(lo), 0.22 + r * math.sin(la), r * math.cos(la) * math.cos(lo), 2 if rnd() < 0.08 else 0])
        for k, (tx, tz) in enumerate([(0.35, 0.2), (1.25, 0.9), (2.1, -0.6)]):
            for i in range(_n(N * 0.09)):
                a = rnd() * TAU; x = math.cos(a) * 0.72; y = g() * 0.01; z = math.sin(a) * 0.72
                y1 = y * math.cos(tx) - z * math.sin(tx); z1 = y * math.sin(tx) + z * math.cos(tx)
                x1 = x * math.cos(tz) - y1 * math.sin(tz); y1 = x * math.sin(tz) + y1 * math.cos(tz)
                push([x1, 0.22 + y1, z1, 2 if k == 1 else 1])
        for b in range(5):
            y = -0.42 - b * 0.16
            for i in range(_n(N * 0.04)):
                e = rnd(); w, h = 0.13, 0.05; side = math.floor(e * 4); t = rnd() * 2 - 1
                pt = [t * w, h] if side == 0 else [t * w, -h] if side == 1 else [-w, t * h] if side == 2 else [w, t * h]
                push([pt[0] + g() * 0.003, y + pt[1] + g() * 0.003, (rnd() - 0.5) * 0.02, 2])
            for i in range(_n(N * 0.006)): push([0, y + 0.05 + rnd() * 0.06, 0, 7])
    elif name == "lifecycle":
        ringN, nodeN, tilt = math.floor(N * 0.34), math.floor(N * 0.05), 0.9
        def on(a, r, lift):
            x, z = math.cos(a) * r, math.sin(a) * r
            return [x, lift + z * math.sin(tilt) * 0.5, z * math.cos(tilt)]
        for i in range(ringN):
            a = rnd() * TAU; r = 0.95 + g() * 0.02; lift = g() * 0.015; p = on(a, r, lift)
            push([p[0], p[1], p[2], 2 if rnd() < 0.15 else 0])
        for n in range(6):
            p = on(n / 6 * TAU + 0.5, 0.95, 0)
            for i in range(nodeN): push([p[0] + g() * 0.045, p[1] + g() * 0.045, p[2] + g() * 0.045, 2 if n == 5 else 0])
        for i in range(_n(N * 0.18)):
            a = rnd() * TAU; r = 0.2 + rnd() * 0.7; p = on(a, r, 0)
            push([p[0] + g() * 0.01, p[1] + g() * 0.01, p[2] + g() * 0.01, 7])
    elif name == "swarm":
        mono = math.floor(N * 0.30)
        for i in range(mono):
            la = math.asin(rnd() * 2 - 1); lo = rnd() * TAU; r = 0.42 * math.pow(rnd(), 0.4)
            push([-0.72 + r * math.cos(la) * math.sin(lo), r * math.sin(la), r * math.cos(la) * math.cos(lo), 1])
        for i in range(_n(N * 0.56)):
            gx = math.floor(rnd() * 7); gy = math.floor(rnd() * 7); gz = math.floor(rnd() * 3)
            push([0.28 + gx * 0.12 + g() * 0.014, -0.42 + gy * 0.14 + g() * 0.014, -0.16 + gz * 0.16 + g() * 0.014, 2 if rnd() < 0.55 else 0])
        for i in range(_n(N * 0.06)): push([-0.2 + g() * 0.01, (rnd() * 2 - 1) * 0.7, (rnd() - 0.5) * 0.3, 7])
    elif name == "boundary":
        per = math.floor(N * 0.085)
        for l in range(8):
            y = 0.7 - l * 0.2
            for i in range(per):
                rim = rnd() < 0.3; x = (rnd() * 2 - 1) * 0.8; z = (rnd() * 2 - 1) * 0.36
                if rim:
                    if rnd() < 0.5: z = (-1 if rnd() < 0.5 else 1) * 0.36
                    else: x = (-1 if rnd() < 0.5 else 1) * 0.8
                push([x + g() * 0.004, y + g() * 0.006, z + g() * 0.004, (2 if rnd() < 0.7 else 0) if l == 2 else (0 if l < 4 else 1)])
        for i in range(_n(N * 0.14)): push([(rnd() * 2 - 1) * 0.92, 0.0 + g() * 0.004, (rnd() * 2 - 1) * 0.46, 2])
    elif name == "rulebook":
        cube = math.floor(N * 0.62)
        for i in range(cube):
            x = (rnd() * 2 - 1) * 0.5; y = (rnd() * 2 - 1) * 0.5; z = (rnd() * 2 - 1) * 0.5
            push([x, y, z, 2] if math.hypot(x, y, z) < 0.22 else [x, y, z, 0 if rnd() < 0.5 else 1])
        for d in range(6):
            a = d / 6 * TAU; cx = math.cos(a) * 1.05; cz = math.sin(a) * 1.05; cy = (d % 3 - 1) * 0.35
            for i in range(_n(N * 0.03)): push([cx + (rnd() - 0.5) * 0.02, cy + (rnd() - 0.5) * 0.22, cz + (rnd() - 0.5) * 0.16, 0])
            for i in range(_n(N * 0.015)):
                t = rnd(); push([cx * (1 - t) + g() * 0.01, cy * (1 - t) + g() * 0.01, cz * (1 - t) + g() * 0.01, 7])
    elif name == "council":
        for i in range(_n(N * 0.18)):
            t = rnd(); a = rnd() * TAU; r = 0.36 + 0.24 * math.sqrt(rnd())
            push([math.cos(a) * r * 0.55 + g() * 0.004, 0.1 + 0.02 * math.sin(a), math.sin(a) * r * 0.55 + g() * 0.004, 0])
        for i in range(_n(N * 0.28)):
            t = rnd(); push([g() * 0.09 * (1 - t) + g() * 0.02, 1.05 - t * 0.9, g() * 0.09 * (1 - t), 1])
        for i in range(_n(N * 0.24)):
            t = rnd(); push([g() * 0.05, 0.05 - t * 1.05, g() * 0.05, 2])
        for i in range(_n(N * 0.09)):
            t = rnd(); push([0.05 + t * 1.1, 0.06 - t * 0.55, g() * 0.03, 3])
        for i in range(_n(N * 0.06)): push([(rnd() * 2 - 1) * 0.6, -1.02 + g() * 0.004, (rnd() * 2 - 1) * 0.3, 2])
    elif name == "ledger":
        blocks = 8
        for b in range(blocks):
            t = b / (blocks - 1); cx = -1.0 + t * 2.0; cy = 0.55 - t * 1.1; cz = math.sin(t * math.pi) * 0.25
            for i in range(_n(N * 0.075)):
                f = math.floor(rnd() * 6); u = rnd() * 2 - 1; v = rnd() * 2 - 1; w, h, d = 0.11, 0.07, 0.07
                pt = ([u * w, v * h, d] if f == 0 else [u * w, v * h, -d] if f == 1 else [u * w, h, v * d] if f == 2 else
                      [u * w, -h, v * d] if f == 3 else [w, u * h, v * d] if f == 4 else [-w, u * h, v * d])
                push([cx + pt[0], cy + pt[1], cz + pt[2], 2 if b == blocks - 1 else 0])
            if b:
                q = (b - 1) / (blocks - 1); px = -1.0 + q * 2.0; py = 0.55 - q * 1.1; pz = math.sin(q * math.pi) * 0.25
                for i in range(_n(N * 0.03)):
                    s = rnd(); push([px + (cx - px) * s + g() * 0.004, py + (cy - py) * s + g() * 0.004, pz + (cz - pz) * s + g() * 0.004, 2])
    elif name == "sessions":
        per = math.floor(N * 0.082); B, F = -0.72, 0.48; U = (F - B) / 10; w = 0.048; H = 0.8 * U; o0 = F + 0.1 * U; o1 = o0 + H
        def cell(r): r *= 10; k = math.floor(r); return B + (k + 0.1 + 0.8 * (r - k)) * U   # hc29: one block per basis point (figure.js)
        for c in range(10):
            x = -1.08 + c * 0.24  # hc7: every column green to the floor, the open unit a khaki outline (figure.js)
            for i in range(per):
                if rnd() < 0.86: push([x + (rnd() - 0.5) * 2 * w, cell(rnd()), (rnd() - 0.5) * 0.1, 2]); continue
                e = rnd() * (4 * w + 2 * H)
                if e < 2 * w: px, py = x - w + e, o0
                elif e < 4 * w: px, py = x - w + (e - 2 * w), o1
                elif e < 4 * w + H: px, py = x - w, o0 + (e - 4 * w)
                else: px, py = x + w, o0 + (e - 4 * w - H)
                push([px + g() * 0.004, py + g() * 0.004, (rnd() - 0.5) * 0.03, 1])
        # award a2: the floor is a rule (RULES), no longer a band of points
    elif name == "mastercopy":
        def sphere(cx, cy, cz, r, n, k):
            for i in range(n):
                la = math.asin(rnd() * 2 - 1); lo = rnd() * TAU; rr = r * math.pow(rnd(), 0.3)
                push([cx + rr * math.cos(la) * math.sin(lo), cy + rr * math.sin(la), cz + rr * math.cos(la) * math.cos(lo), k])
        sphere(0, 0.6, 0, 0.3, math.floor(N * 0.28), 2)
        for c in range(5):
            a = (c / 4 - 0.5) * 2.4; cx = math.sin(a) * 1.0; cy = -0.35; cz = math.cos(a) * 0.35 - 0.2
            sphere(cx, cy, cz, 0.17, math.floor(N * 0.07), 0 if c == 0 else 1)
            for i in range(_n(N * 0.035)):
                s = rnd(); push([cx * s + g() * 0.006, 0.6 + (cy - 0.6) * s + g() * 0.006, cz * s + g() * 0.006, 7])
        for i in range(_n(N * 0.1)): push([(rnd() * 2 - 1) * 1.3, -0.75 + g() * 0.004, (rnd() * 2 - 1) * 0.5, 1])
    else:
        raise KeyError(name)
    return P[:N]
FIT_JS = {"lifecycle": 1.16, "rulebook": 1.12}  # figure.js FIT: the flat ring and the small cube are drawn larger
def _camera(fig):
    """figure.js's camera as the plate rests: a point of the formation (its own space) to the hero stage's units (its
    height is 400, centred) and the depth term v2"""
    f, eye, S0 = 1 / math.tan(0.31), (0.0, 0.35, 4.4), 0.84 * FIT_JS.get(fig, 1)
    n = math.hypot(*eye); zx, zy, zz = (e / n for e in eye)
    xx, xz = zz, -zx; n = math.hypot(xx, xz) or 1; xx, xz = xx / n, xz / n
    yx, yy, yz = zy * xz, zz * xx - zx * xz, -zy * xx
    def proj(px, py, pz):
        x, y, z = px * S0, py * S0, pz * S0
        v0 = xx * x + xz * z - (xx * eye[0] + xz * eye[2])
        v1 = yx * x + yy * y + yz * z - (yx * eye[0] + yy * eye[1] + yz * eye[2])
        v2 = zx * x + zy * y + zz * z - (zx * eye[0] + zy * eye[1] + zz * eye[2])
        return 200 * f * v0 / -v2, -200 * f * v1 / -v2, v2  # the stage's height is 400 units, centred
    return proj
def _projected(fig, model=False):
    """the note's formation as the plate rests: every point that is not dust, projected (x, y in units where the hero
    stage's height is 400, centred; depth 0..1, nearer the eye brighter; kind; with model=True also the point in the
    formation's own space, for PARTS), and the plate's rules (RULES) as lines"""
    N = 15000; r = _rng(len(fig) * 977 + 13)
    g = lambda: (r() + r() + r() - 1.5) * 0.82
    pts = _forms(fig, N, r, g)
    proj = _camera(fig)
    dots = []
    for p in pts:
        if p[3] >= 7: continue
        sx, sy, v2 = proj(p[0], p[1], p[2])
        d = (sx, sy, min(1, max(0, (v2 + 5.6) / 2.6)), p[3])  # figure.js: nearer the eye, brighter
        dots.append(d + (tuple(p[:3]),) if model else d)
    rules = [(proj(*a)[:2], proj(*b)[:2]) for a, b in RULES.get(fig, [])]
    return dots, rules
def note_still(fig, every=7):
    """the note's formation as a still: dots where the plate's points land at rest (see the comment above _rng)"""
    dots, rules = _projected(fig)
    paths, xm = {}, 0.0
    # award a4 (r4): the bright half is the nearer half of the drawing (its own median depth), as the margin plate's since
    # a3. A fixed 0.5 put every point of note 09's columns, the council's stream and the copies on the dim side (none of
    # 09's 1,757 dots was "near"): its columns read mid-grey, dimmer than the live drawing they stand in for
    med = sorted(d[2] for i, d in enumerate(dots, 1) if not i % every)[len(dots) // every // 2]
    for i, (sx, sy, depth, k) in enumerate(dots, 1):
        if i % every: continue
        xm = max(xm, abs(sx))
        paths.setdefault((k, depth > med), set()).add((round(sx), round(sy)))
    # award budgets: each path's dots once (2,706 of the ten stills' dots repeated a dot of their own path) and in column
    # order, each from the one before it (m dx dy), as the margin plates are written: the same dots in the same places, so
    # the same picture (one path is one stroke: neither order nor a repeat changes a pixel), in 20.4 KB of gzip for the
    # ten notes, not 46.8 (the notes' HTML -2.6 KB each on average; note 02 13.6 -> 10.7 KB, inside a first round trip)
    num = lambda v: str(v) if v < 0 else f" {v}"
    def rel(pts):
        dd, px, py = [], None, None
        for x, y in sorted(pts):
            dd.append(f"M{x} {y}h0" if px is None else f"m{x - px}{num(y - py)}h0"); px, py = x, y
        return "".join(dd)
    # award a2: the plate's rules (RULES: note 09's floor) as lines, a hairline at any scale (research.css .fs-still .rule)
    xm = max([xm] + [abs(q[0]) for ln in rules for q in ln])
    w = math.ceil(xm + 12)
    body = "".join(f'<path class="k{k}{" far" if not near else ""}" d="{rel(d)}"/>' for (k, near), d in sorted(paths.items()))
    body += "".join(f'<path class="rule{_base(fig, i)}" d="M{a[0]:.1f} {a[1]:.1f}L{b[0]:.1f} {b[1]:.1f}"/>' for i, (a, b) in enumerate(rules))
    return (f'<svg class="fs-still" viewBox="{-w} -200 {2 * w} 400" preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false">'
            f'{body}</svg>')
# award a4 (a4-pixel, polish): a figure whose labels are its key (note 09: the floor and its value, the 01-10 axis, and so,
# by r3's rule, the hedge label "above the floor / exact value not published") keeps that key on its still, where figure.js
# cannot set the labels (no JavaScript, no WebGL), and on the margin plate. Same words, sides and flags as LABELS
KEYED = {"sessions"}
def _fl(lab, style, cls="", attrs="", plate=False):
    """one label as static markup, in figure.js's .fl grammar (research.css): the point, its rule and the words. On a
    margin plate (plate=True) a gloss ("minorsub") is dropped, as on a small stage; a hedge (keep) never is"""
    text, sub, _at, side, flags = lab[:5]
    k = _keep(flags); fl = flags.split()
    if plate and "minorsub" in fl: sub = None
    c = "".join(f" fl--{f}" for f in fl if not f.endswith("sub") and f != k)
    small = _small(sub, fl)
    return f'<span class="fl{c}{cls}" data-side="{side}"{attrs} style="{style}"><span class="fl-t">{H.escape(text, quote=False)}{small}</span></span>'
def still_keys(fig):
    """the key over the hero's still (KEYED): each label at its point in the still's own units (the viewBox: the stage's
    height is 400, centred), placed by research.css from the stage's size (.fs-keys: shown without JavaScript and when
    figure.js cannot draw; figure.js sets its own labels over the live drawing)"""
    if fig not in KEYED: return ""
    proj = _camera(fig)
    out = []
    for lab in LABELS[fig]:
        x, y, _ = proj(*lab[2])
        out.append(_fl(lab, f"--x:{x:.1f};--y:{y:.1f}"))
    return f'<div class="fs-keys" aria-hidden="true">{"".join(out)}</div>'
def still_geo(fig, every=7):
    """award a3 (4K inspector): where the hero still's drawing lies in its stage, for the caption without JavaScript (or
    WebGL). research.css hangs the hedge under the drawing's left edge, as figure.js does with the live drawing (--fig-l,
    --fig-b), from three numbers in units of the stage's height (the viewBox's 400): the viewBox's width (--fs-w), how far
    the drawing reaches left of the centre (--fs-x) and below it (--fs-y). Every point counts, as figure.js's edge sample.
    award a4: a keyed still (KEYED) also gives the viewBox's width in its units (--fs-vbw), for its labels, and the hedge
    hangs under the key's words"""
    dots, rules = _projected(fig)
    xm = max([abs(d[0]) for i, d in enumerate(dots, 1) if not i % every] + [abs(q[0]) for ln in rules for q in ln])
    x0 = min([d[0] for d in dots] + [q[0] for ln in rules for q in ln]); y1 = max(d[1] for d in dots)
    vbw = 2 * math.ceil(xm + 12)
    if fig not in KEYED: return f"--fs-w:{vbw / 400:.4f};--fs-x:{-x0 / 400:.4f};--fs-y:{y1 / 400:.4f}"
    # the hedge hangs under the key's lowest words (the axis): their point, then 18 px of rule and a 15 px line (--fs-kb)
    proj = _camera(fig); y1 = max([y1] + [proj(*l[2])[1] for l in LABELS[fig] if l[3] == "b"])
    return f"--fs-w:{vbw / 400:.4f};--fs-x:{-x0 / 400:.4f};--fs-y:{y1 / 400:.4f};--fs-vbw:{vbw};--fs-kb:2.0625rem"
# award a4 (a4-design, medium: "the figure follows the argument"): the part of a note's drawing that a part of the note
# names. While "In this note" marks that part (research.js), the margin plate lights it: its dots at full strength over
# the rest of the drawing, which recedes, and its label (the hero's words, LABELS) beside it, in the figure.js pulse's
# grammar (.is-lit). Only where the note's own text names a part the drawing has (its heading or its words); every other
# part of the note shows the whole still, as before. Keys: the part heads, word for word (the build stops otherwise);
# the label LABELS names; which of the formation's points are that part (figure.js FORMS: x, y, z, kind; None: the
# plate's rule, note 09's floor). No new data and no new words: a label the hero already shows, a part already drawn
PARTS = {
    "horizon": [("The problem is horizon, not capability", "p to the power n", lambda x, y, z, k: k == 0),  # "p to the n"
                ("Decomposition changes the exponent", "A gate after every step", lambda x, y, z, k: k in (1, 2))],  # the gate after step k
    "weights": [("Post-training moves the rulebook into the weights", "One base model", lambda x, y, z, k: math.hypot(x, y - 0.22, z) < 0.5),
                ("Parameter-efficient specialization and the forgetting problem", "Adapters", lambda x, y, z, k: 0.71 < math.hypot(x, y - 0.22, z) < 0.73),
                (("Part two: proving what happened", "What must go in the record", "Replay as off-policy evaluation"), "The record", lambda x, y, z, k: y < -0.36)],
    "swarm": [("The verification argument", "One gate, one job each", lambda x, y, z, k: x > 0.15)],  # "small agents are verifiable ... at which gate"
    "boundary": [(("Why the boundary sits there", "MCP as the structural interface"), "The boundary", lambda x, y, z, k: abs(y) < 0.03),
                 ("Idempotency as a safety property", "05–08 Execute", lambda x, y, z, k: y < -0.05)],  # "the execution layer"
    "rulebook": [("Exceptions are the training set", "Documents, exceptions", lambda x, y, z, k: math.hypot(x, z) > 0.9),
                 ("Why this creates a defensible position", "The post-trained model", lambda x, y, z, k: math.hypot(x, z) < 0.8)],  # "a post-trained model is a moat"
    "council": [("What the council checks", "Execution Council", lambda x, y, z, k: k == 0),
                ("Three operating modes", "Approved", lambda x, y, z, k: k == 2 and y > -1.0),  # "every approved proposal"
                ("Conflict arbitration", "Proposals", lambda x, y, z, k: k == 1)],  # "two decision agents propose actions"
    "ledger": [("Why append-only", "Hash of the previous record", lambda x, y, z, k: k == 2 and not (x > 0.885 and y < -0.475))],  # the links, not the newest block
    "sessions": [("The result", "Floor", None)],  # "every one above the floor we set of ten basis points": the rule
    "mastercopy": [("Phase one: prove one", "Master agent", lambda x, y, z, k: k == 2),
                   ("Phase two: master and copy", "Copies", lambda x, y, z, k: k in (0, 1) and y > -0.6)],
}
# a label's words beside its point on a margin plate, in CSS px where the plate is narrowest (1440: 278 px for its 300
# units); research.css .fl / .fl-t: Inter at --fs-small (14 px at 1440; hc3, was 11 px mono), a numeral alone or a value
# line (n, nsub) 11 px mono (an advance of .64 em with the tracking), 1.35 leading, the rule's 19 px lead beside the
# point, 18 px above or below it, the tl/tr words 6 px past it. Where no side fits, the box grows. Inter's advances
# (thousandths of an em, measured in Chromium from the vendored inter-var-latin.woff2; digits at their tabular width;
# kerning only narrows a word, so the box is never short)
_PU, _FS, _FN = 278 / 300, 14, 11
_ADV = {**dict(zip("abcdefghijklmnopqrstuvwxyz", (562, 612, 571, 612, 583, 370, 613, 591, 242, 242, 549, 242, 876, 591, 600, 612,
                                                 612, 376, 528, 327, 591, 562, 818, 546, 562, 552))),
        **dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (690, 654, 730, 722, 601, 590, 746, 743, 269, 571, 672, 565, 903, 753, 765, 639,
                                                 765, 644, 642, 646, 744, 690, 985, 682, 679, 629))),
        **{c: 650 for c in "0123456789"}, " ": 281, "\u00a0": 281, ",": 288, ".": 288, "-": 460, "–": 500}
def _tw(t, mono=False): return len(t) * 0.64 * _FN if mono else sum(_ADV.get(c, 1000) for c in t) / 1000 * _FS
_NEAR = {"r": "tr br l tl bl t b", "l": "tl bl r tr br t b", "t": "tl tr b bl br r l", "b": "bl br t tl tr l r",
         "tl": "t tr l bl r", "tr": "t tl r br l", "bl": "b br l tl r", "br": "b bl r tr l"}
_NEAR = {k: v.split() for k, v in _NEAR.items()}
# where a part's label stands on the small plate when the hero's point would put its words on its own part or past the
# plate's edge: another point of the same part (the formation's own space) and its side. "Hash of the previous record"
# on the link between records 02 and 03 (since hc3 the hero's point too), its words in the empty corner above the chain;
# "05-08 execute" under the lowest layer; "one base model" over the sphere's top (beside its left edge the words took a third of the plate);
# hc3: "Adapters" up and right from a point of the middle ring (Inter's taller line no longer fit beside the ring's right
# edge, and the box grew right: the unlit drawing stood 26 units left of centre)
PLATE_AT = {"Hash of the previous record": ((-0.571, 0.314, 0.156), "tr"), "05–08 Execute": ((0.0, -0.71, 0.0), "b"),
            "One base model": ((0.0, 0.68, 0.0), "t"), "Adapters": ((0.526, 0.711, 0.036), "tr")}
def _lbox(side, ax, ay, w, h, em=_FS):
    if side in ("r", "l"):  # the first line on the rule (research.css: translate(.., -.675em))
        x0 = ax + 19 if side == "r" else ax - 19 - w
        return x0, ay - 0.675 * em, x0 + w, ay - 0.675 * em + h
    y0 = ay - 18 - h if side[0] == "t" else ay + 18
    x0 = ax - w / 2 if len(side) == 1 else ax + 6 - w if side[1] == "l" else ax - 6
    return x0, y0, x0 + w, y0 + h
def margin_still(fig, slugs=(), every=5):
    """award a3 (a3-design, big): the margin plate beside a note's text (from 1440 px; research.css .np-rail) is the
    note's own still, drawn again for its size: the drawing cropped to its own extent (plus a margin), every 5th point
    (the hero's still has every 7th over four times the area: at this size the plate needs more to read as the same
    drawing, not dust), at the same depth and colour steps; the box's shape is the drawing's, between square and 8:5, so
    a flat ring and a tall council both fill their plate. Each dot is a relative move in a 300-wide box.
    It is a file (site/assets/img/research/plate-<fig>.svg, presentation attributes in the tokens' values: no style
    element, so the CSP's style-src holds for it too), not inline: inline it took note 02's HTML from 13.3 to 16.7 KB
    gzip, past the first round trip (Lighthouse FCP +120 ms on every note); as a lazy <img> in a rail that phones never
    show, a phone never fetches it. Its dots scale with the plate (2 px at 1440, 5 at 3840 = 1920 doubled). A plate's
    rule (note 09's floor) is not in the file: research.css draws it over the image as a hairline (--hair), crisp at any
    density. Returns the <img> (and the rule) for the note's markup. Its caption is the hero's (cap_html: the hedge).
    award a4: each part a part of the note names (PARTS) is a second file, plate-<fig>-<n>.svg: the same dots of that
    part, at full strength, laid over the still and shown while the note's contents mark that part (research.js;
    research.css .np-part); its label stands beside it then. A keyed figure (KEYED: note 09) carries its key on the plate
    at all times. The box grows until every label it may show fits inside it at 1440, on its own side or the next free one"""
    dots, rules = _projected(fig, model=True)
    pick = [d for i, d in enumerate(dots, 1) if not i % every]
    proj = _camera(fig)
    byname = {l[0]: l for l in LABELS[fig]}
    parts = []
    for heads_, name, test in PARTS.get(fig, []):
        hs = heads_ if isinstance(heads_, tuple) else (heads_,)
        for h_ in hs: assert slugify(h_) in slugs, f"PARTS[{fig!r}]: “{h_}” is not a part head of its note"
        parts.append((" ".join(slugify(h_) for h_ in hs), byname[name], test))
    # the labels the plate may show: the key (always), each part's label (while lit); a key label a part names is lit too
    labs = {}
    if fig in KEYED:
        for l in LABELS[fig]:
            if "minor" not in l[4].split(): labs[l[0]] = [l, True, [], []]
    for ss, l, test in parts:
        e = labs.setdefault(l[0], [l, False, [], []]); e[2].append(ss)
        if test: e[3].append(test)
    xs = [d[0] for d in pick] + [q[0] for ln in rules for q in ln]; ys = [d[1] for d in pick] + [q[1] for ln in rules for q in ln]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    for _ in range(16):
        w, h = x1 - x0, y1 - y0
        W, H = w * 1.16, h * 1.2  # the drawing with a margin; then the box's shape clamped to 1:1 .. 8:5 (a tall drawing in
        W = max(W, H); H = max(H, W / 1.6)  # a square, a flat one in an 8:5 box, centred)
        s = 300 / W; hb = round(H * s)
        ox, oy = (x0 + x1) / 2, (y0 + y1) / 2
        fx = lambda x: (x - ox) * s + 150; fy = lambda y: (y - oy) * s + H * s / 2
        placed, grow = [], [0.0, 0.0, 0.0, 0.0]
        for l, perm, sss, tests in labs.values():
            text, sub, at, side, flags = l[:5]
            if "minorsub" in flags.split(): sub = None
            k = _keep(flags); allowed = k.partition("=")[2].split(",") if k and "=" in k else None
            if l[0] in PLATE_AT: at, side = PLATE_AT[l[0]]
            ax, ay = proj(*at)[:2]
            px, py = fx(ax) * _PU, fy(ay) * _PU
            fl_ = flags.split(); em = _FN if "n" in fl_ else _FS
            tw = max(_tw(text, "n" in fl_), _tw(sub, "nsub" in fl_) if sub else 0)
            th = 1.35 * em + (1.35 * (_FN if "nsub" in fl_ else _FS) if sub else 0)
            # a key keeps the hero's side (its own, or a hedge's allowed ones); a part's label, shown only while the rest
            # of the drawing recedes, may take another side round its point, so long as no dot of its own part is under
            # its words
            order = [side] + [sd for sd in (allowed or (() if perm else _NEAR[side])) if sd != side]
            lit_px = [(fx(d[0]) * _PU, fy(d[1]) * _PU) for d in pick if any(t(*d[4], d[3]) for t in tests)]
            under = lambda b: sum(1 for x, y in lit_px if b[0] - 3 <= x <= b[2] + 3 and b[1] - 3 <= y <= b[3] + 3)
            for sd in order:
                b = _lbox(sd, px, py, tw, th, em)
                if b[0] >= 4 and b[1] >= 4 and b[2] <= 300 * _PU - 4 and b[3] <= hb * _PU - 4 and not under(b):
                    placed.append((l, perm, sss, sd, ax, ay)); break
            else:  # no side fits: the drawing's extent grows, on the side that keeps the drawing largest (a taller box
                # costs nothing while the box is wider than tall; a wider one shrinks the drawing)
                P, best = s * _PU, None
                for sd in [sd for sd in order if not under(_lbox(sd, px, py, tw, th, em))] or order[:1]:
                    b = _lbox(sd, px, py, tw, th, em)
                    g = [max(0.0, (4 - b[0]) / P), max(0.0, (b[2] - 300 * _PU + 4) / P), max(0.0, (4 - b[1]) / P), max(0.0, (b[3] - hb * _PU + 4) / P)]
                    w2, h2 = (x1 - x0) + g[0] + g[1], (y1 - y0) + g[2] + g[3]
                    sc = 1 / max(w2 * 1.16, h2 * 1.2)
                    if best is None or sc > best[0] + 1e-9: best = (sc, g)
                grow = [max(a, b) for a, b in zip(grow, best[1])]
        if not any(g > 0 for g in grow): break
        x0 -= max(0.0, grow[0]) + 0.5 * (grow[0] > 0); x1 += max(0.0, grow[1]) + 0.5 * (grow[1] > 0); y0 -= max(0.0, grow[2]) + 0.5 * (grow[2] > 0); y1 += max(0.0, grow[3]) + 0.5 * (grow[3] > 0)
    else:
        raise AssertionError(f"margin_still({fig!r}): a label does not fit its plate")
    X = lambda x: round(fx(x)); Y = lambda y: round(fy(y))
    # pass 3: nearer than the drawing's own median depth is the bright half (a fixed 0.5 left note 09's columns and the
    # council all "far": grey, and dimmer than the hero they repeat)
    med = sorted(d[2] for d in pick)[len(pick) // 2]
    num = lambda v: str(v) if v < 0 else f" {v}"
    # site.css's tokens: --paper, --khaki, --signal-bright, --reject-bright (the hero still's .fs-still .k0-.k3)
    COL = {0: "#F5F2EC", 1: "#ACA68E", 2: "#4FCB93", 3: "#D9675D"}
    def svg(name, sel, op):
        groups = {}
        for d in sel: groups.setdefault((d[3], d[2] > med), set()).add((Y(d[1]), X(d[0])))
        paths = []
        for (k, near), pts in sorted(groups.items()):
            dd, px, py = [], None, None
            for y, x in sorted(pts):
                dd.append(f"M{x} {y}h0" if px is None else f"m{x - px}{num(y - py)}h0"); px, py = x, y
            paths.append(f'<path stroke="{COL[k]}" stroke-opacity="{op(k, near)}" d="{"".join(dd)}"/>')
        write(os.path.join(ROOT, "assets", "img", "research", name),
              f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 {hb}" width="300" height="{hb}"><g fill="none" stroke-width="2.16" stroke-linecap="round">'
              + "".join(paths) + "</g></svg>\n")
    svg(f"plate-{fig}.svg", pick, lambda k, near: {(2, True): ".95", (2, False): ".74"}.get((k, near), ".9" if near else ".58"))
    lit = {}  # the rule's parts
    out = [f'<img class="np-still" src="../assets/img/research/plate-{fig}.svg" width="300" height="{hb}" alt="" loading="lazy" decoding="async">']
    for n, (ss, l, test) in enumerate(parts, 1):
        if test is None: lit.setdefault("rule", []).append(ss); continue
        sel = [d for d in pick if test(*d[4], d[3])]
        assert sel, f"PARTS[{fig!r}]: “{l[0]}” selects no point"
        svg(f"plate-{fig}-{n}.svg", sel, lambda k, near: "1" if near or k == 2 else ".8")  # the part at full strength
        out.append(f'<img class="np-part" data-parts="{ss}" src="../assets/img/research/plate-{fig}-{n}.svg" width="300" height="{hb}" alt="" loading="lazy" decoding="async">')
    rp = f' data-parts="{" ".join(lit["rule"])}"' if "rule" in lit else ""
    out += [f'<i class="np-rule{_base(fig, i)}"{"" if _base(fig, i) else rp} style="--y:{fy(a[1]) / hb * 100:.2f}%;--x0:{fx(a[0]) / 3:.2f}%;--x1:{fx(b[0]) / 3:.2f}%"></i>' for i, (a, b) in enumerate(rules)]
    for l, perm, sss, sd, ax, ay in placed:
        out.append(_fl((l[0], l[1], l[2], sd, l[4]), f"--x:{fx(ax) / 3:.2f}%;--y:{fy(ay) / hb * 100:.2f}%", " np-key" if perm else "",
                       f' data-parts="{" ".join(sss)}"' if sss else "", plate=True))
    return "".join(out)
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
    <section class="page-hero page-hero--dark is-dark grain article-hero" style="{still_geo(post['fig'])}">
      <div class="figure-stage article-figure has-still" data-figure="{post['fig']}" data-spin="0.10" data-plate data-rest="2.5" data-bbox data-vt-dest aria-hidden="true">{note_still(post['fig'])}{still_keys(post['fig'])}<canvas></canvas>{labels_html(post['fig'])}</div>
      <div class="container">
        <div class="article-hero-grid">
          <div>
            <h1 class="display-1 article-title{' article-title--long' if long_title else ''}{' article-title--split' if 't-head' in title_html(title) else ''}" data-reveal data-split>{title_html(title)}</h1>
            <div class="article-meta" data-reveal style="--d:120ms"><span>Founder’s notes</span><span>{post['minutes']}{NB}min read</span></div>
          </div>
          {cap_html(post['fig'], "figcap article-figcap", attrs=" data-hang")}
        </div>
      </div>
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
          <div class="np-rail" aria-hidden="true"><figure class="np-plate"><div class="np-stage is-dark">{margin_still(post['fig'], {a for a, _ in heads})}</div><figcaption>{cap_html(post['fig'], "figcap np-cap")}</figcaption></figure></div>
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
            <div class="rs-stage is-dark grain"><div class="figure-stage" id="research-figure" data-figure="{ordered[0]['fig']}" data-spin="0.07" data-rest="2.5" data-plate><canvas></canvas>{"".join(labels_html(p['fig']) for p in ordered)}</div></div>
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
