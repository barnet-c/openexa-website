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
   note 02's body). Bodies, titles and read times are unchanged."""
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

# v2x (30 Oct): every figure has a caption written from its own note (PAGES.md §6.3, FC-01..FC-10; owner approval is
# pending, so they are listed in REPORT.md). Per formation: the line that says what is drawn, the note's own words
# (each “quoted” passage must occur verbatim in that note: the build stops otherwise), and the hedge line.
NB = " "
CAPTIONS = {
    "horizon": ("Two runs of dependent steps, one of them gated.",
                "The ungated run decays as p to the power n. The gated run has a gate after every step. “An error at step k is caught at the verification gate after step k.”",
                "Illustrative"),
    "weights": ("One base model, rings of adapters, the record below.",
                "“One base model, many adapters.” Each record in the chain below holds “the hash of the previous record.”",
                "Illustrative"),
    "lifecycle": ("A lifecycle as one loop of gates, the last one lit.",
                  "A lifecycle “starts with a signal, moves through a series of decisions and approvals, executes against an external counterparty, and ends with a record”.",
                  "Illustrative"),
    "swarm": ("One large agent beside a lattice of small ones.",
              "“No single agent sees the whole trade. Each agent is scoped to exactly one gate in the lifecycle and does exactly one job.”",
              "Illustrative"),
    "boundary": ("Eight layers and one bright plane between them.",
                 "“The top four decide.” Under the plane: “The bottom four execute, and they are deterministic code.”",
                 "Illustrative"),
    "rulebook": ("A dense core, with documents drifting in.",
                 "“The most valuable data in any lifecycle is its exception history.”",
                 "Illustrative"),
    "council": ("Proposals arrive from above; rejected ones leave to the side.",
                "Approved proposals continue down. “If any check fails, the proposal exits at the gate and is logged.”",
                "Illustrative"),
    "ledger": ("Eight blocks in a chain, each linked to the one before.",
               "The newest block is lit. “Editing any entry breaks verification for every entry after it.”",
               "Illustrative"),
    # note 09: the colours are the record's (data-regimes, from #oxa-sessions); the floor line is not a scale
    # r2 (r2-copy minor): the last clause untangled; the hedge ("how far is not published") stays beside its claim
    "sessions": ("Ten sessions, one column each, in the order of the record.",
                 f"Green for a premium regime, ivory for discount. Each column fills to the khaki line, the 10{NB}bps floor, and every one rises past it. How far is not published, so the scatter above the line is drawn, not measured.",
                 "Illustrative · heights not to scale · regimes read from the record"),
    "mastercopy": ("One proven agent above, its copies below, on one control plane.",
                   "Phase two, on the roadmap. “A copy is a replication of that agent onto a new asset or strategy under the same control plane.”",
                   "Illustrative · roadmap"),
}
# r2 (r2-copy minor): the figure's labels ("01–02 research notes", "03–10 the series") and the meta row already say which
# leaves are which, so the caption says what the drawing is, once
# r3 (r3-art minor): set in the plate captions' register, as on Platform, Lifecycles, Proof and Trust ("Plate · Six
# lifecycle classes · Schematic"): the "Plate" mark, the title (no full stop, as theirs), the hedge
LIBRARY_CAPTION = ("Ten notes as ten leaves", "Illustrative")
# v2x lab (research moment): every figure is read as a plate. Its labels pin to points of the formation (figure.js, a
# stage with data-plate projects data-at, the formation's own x,y,z, onto the screen each frame) and say what each part
# is, in the words of its caption or its note: no new fact, no number the caption does not already state. Points are
# figure.js's geometry (FORMS): a formation that moves needs its labels moved here. Sides: r, l (text beside the point,
# its first line on the rule), t, b (centred above, below), tl, tr, bl, br (above or below, text ending or starting at
# the point). Flags: "minor" (dropped on a small stage), "minorsub" (its second line, a gloss, dropped on a small stage;
# never for a hedge), "acc" (the green part), "rej" (a rejection: the only red text). An optional last item (r1) is where
# the words begin when the point lies inside the drawing: the rule reaches out to it (figure.js data-to, --lead).
# Path: the span of the formation's own path (FORMS' fifth value, 0..1) the label names; while the pulse walks the
# path it lights each label it passes, so the plate reads itself out in the note's order. None: the part is not on
# the path (it is named, never lit).
# r3 (r3-a11y moderate): "keep" marks a label that carries a hedge (note 09 "how far is not published", note 10 "phase
# two, on the roadmap"). It is listed first, so where words would cross, the claim-side label yields to it; where its
# own side has no room (a phone's stage), figure.js looks for another free slot round its point; and if there is none,
# the plate shows no labels at all, so a drawing never names its parts without their hedge (data-keep). "keep=t,tl,tr"
# limits the slots to those sides: "above the floor" never stands below the columns it describes.
def _cols():  # note 09: ten columns, x = -1.08 + c * 0.24 (figure.js sessions), numbered and lit in the record's order
    return [(f"{c + 1:02d}", None, (round(-1.08 + c * 0.24, 2), -0.76, 0), "b", "" if c in (0, 9) else "minor", (c / 10, (c + 0.9) / 10))
            for c in range(10)]
def _loop(n):  # note 03: node n of figure.js lifecycle (a ring of r 0.95, tilted 0.9, from angle 0.5)
    a = n / 6 * math.tau + 0.5; x, z = math.cos(a) * 0.95, math.sin(a) * 0.95
    return (round(x, 3), round(z * math.sin(0.9) * 0.5, 3), round(z * math.cos(0.9), 3))
LABELS = {
    "horizon": [("verification gate", None, (-0.69, -0.74, 0.14), "b", "", (0.2, 0.2)),
                ("a gate after every step", None, (0.72, 0.57, 0.14), "t", "acc", (0.81, 0.81)),
                ("p to the power n", None, (0.92, -0.55, -0.12), "b", "", (0.9, 0.9))],
    "weights": [("one base model", None, (-0.46, 0.22, 0), "l", "", None, (-0.84, 0.22, 0)),
                ("adapters", None, (0.705, 0.363, 0), "r", "", (0.0, 0.5)),
                ("the record", "each holds the previous hash", (0.14, -0.74, 0), "r", "minorsub", (0.55, 0.95))],
    # the note's own definition of a lifecycle, in its order round the loop
    "lifecycle": [("signal", None, _loop(0), "r", "", (0.0, 0.03)),
                  ("decisions, approvals", None, _loop(2), "l", "", (0.18, 0.56)),
                  ("executes against an external counterparty", None, _loop(4), "b", "minor", (0.74, 0.74)),
                  ("record", None, _loop(5), "r", "acc", (0.93, 0.93))],
    "swarm": [("one large agent", None, (-0.72, 0.45, 0), "t", "", None),
              ("one gate, one job each", None, (0.64, 0.46, 0), "t", "acc", None)],
    "boundary": [("01–04 decide", None, (-0.8, 0.4, 0.36), "l", "", (0.0, 0.34)),
                 ("the boundary", None, (-0.92, 0, 0.46), "l", "acc", (0.44, 0.44)),
                 ("05–08 execute", "deterministic code", (-0.8, -0.4, 0.36), "l", "minorsub", (0.55, 0.89))],
    "rulebook": [("documents, exceptions", None, (1.05, -0.47, 0), "b", "", (0.08, 0.2)),
                 ("the post-trained model", None, (0, 0.52, 0), "t", "", (0.96, 0.96))],
    "council": [("proposals", None, (0.02, 0.95, 0), "r", "", (0.0, 0.1)),
                ("Execution Council", None, (-0.34, 0.1, 0), "l", "", (0.42, 0.42)),
                ("approved", None, (0, -0.86, 0), "l", "acc", (0.84, 0.92)),
                ("rejected, logged", None, (1.15, -0.5, 0), "b", "rej", (0.9, 0.9))],
    "ledger": [("record 01", None, (-1.0, 0.63, 0), "t", "", (0.0, 0.06)),
               ("hash of the previous record", None, (0, 0.02, 0.24), "tr", "", (0.43, 0.45)),
               ("newest", None, (1.0, -0.63, 0), "b", "acc", (0.875, 0.9))],
    # the floor is read like an axis: its value at the line's left end, the first line on the rule
    # r3: each hedge label first ("keep", below)
    "sessions": [("above the floor", "how far is not published", (0, 0.93, 0), "t", "keep=t,tl,tr", None),
                 ("10\u00a0bps", "floor", (-1.25, 0.4, 0.07), "l", "", None)] + _cols(),
    "mastercopy": [("copies", "phase two, on the roadmap", (0.93, -0.18, -0.07), "tl", "keep", (0.74, 0.74)),
                   ("master agent", None, (0.31, 0.62, 0), "r", "acc", (0.0, 0.06)),
                   ("one control plane", None, (-1.3, -0.77, 0), "br", "", (0.9, 0.9))],
    "library": [("01–02 research notes", None, (-0.873, 0.47, 0.095), "t", "acc", (0.0, 0.16)),
                ("03–10 the series", None, (0.873, 0.47, 0.095), "t", "", (0.19, 0.9))],
}
def _keep(flags): return next((f for f in flags.split() if f.split("=")[0] == "keep"), None)
assert all(not _keep(l[4]) for ls in LABELS.values() for l in ls[1:]), "a hedge label (keep) is listed first"
def labels_html(fig):
    out = []
    for i, (text, sub, (x, y, z), side, flags, path, *to) in enumerate(LABELS[fig]):
        k = _keep(flags)
        cls = "".join(f" fl--{f}" for f in flags.split() if f != "minorsub" and f != k)
        keep = (f' data-keep="{k.partition("=")[2].replace(",", " ")}"' if "=" in k else " data-keep") if k else ""
        gloss = ' class="fl-minor"' if "minorsub" in flags.split() else ""
        small = f"<small{gloss}>{H.escape(sub, quote=False)}</small>" if sub else ""
        ph = f' data-ph="{path[0]:g},{path[1]:g}"' if path else ""
        reach = f' data-to="{to[0][0]:g},{to[0][1]:g},{to[0][2]:g}"' if to else ""
        out.append(f'<span class="fl{cls}" data-at="{x:g},{y:g},{z:g}"{reach} data-side="{side}"{ph}{keep} style="--i:{i}"><span class="fl-t">{H.escape(text, quote=False)}{small}</span></span>')
    return f'<div class="fig-labels" data-for="{fig}">{"".join(out)}</div>'
def library_still():
    """r2 (r2-art minor): the index hero's figure as a still, in the page's HTML. v2 and r1 painted nothing there until
    WebGL drew (and nothing at all without JavaScript or WebGL), the only inner first screen without a drawing. This is
    the same formation as figure.js's 'library' (ten leaves fanned round one spine, the two research notes lit), seen by
    the same camera in the pose the plate's first frame takes (face-on, eye 0, 0.35, 4.4; fov 0.62; scale .92, the
    desktop --figure-scale), engraved as ruled leaves instead of points: each leaf its outline and seven rules. Units: the
    stage's height is 200, centred, so with xMidYMid meet the still lies where the points land (research.css scales it as
    the stage's --figure-scale scales the points). When the WebGL figure is drawn (.figure-ready) the still fades out under
    it; without JavaScript or WebGL it stays, with its caption. Geometry from figure.js FORMS.library and lookAt(): a
    change there needs this looked at."""
    f, eye, S0 = 1 / math.tan(0.31), (0.0, 0.35, 4.4), 0.92
    n = math.hypot(*eye); zx, zy, zz = (e / n for e in eye)
    xx, xz = zz, -zx; n = math.hypot(xx, xz) or 1; xx, xz = xx / n, xz / n
    yx, yy, yz = zy * xz, zz * xx - zx * xz, -zy * xx
    def p(x, y, z):
        x, y, z = x * S0, y * S0, z * S0
        v0 = xx * x + xz * z - (xx * eye[0] + xz * eye[2])
        v1 = yx * x + yy * y + yz * z - (yx * eye[0] + yy * eye[1] + yz * eye[2])
        v2 = zx * x + zy * y + zz * z - (zx * eye[0] + zy * eye[1] + zz * eye[2])
        return 100 * f * v0 / -v2, -100 * f * v1 / -v2, v2
    def pt(a, u, v): return p(math.sin(a) * u, v * 0.46, math.cos(a) * u - 0.35)
    leaves, xm = [], 0.0
    for l in range(10):
        a = (l / 9 - 0.5) * 2.2
        rim = [pt(a, u, v) for u, v in ((0.12, -1), (0.98, -1), (0.98, 1), (0.12, 1))]
        xm = max(xm, *(abs(q[0]) for q in rim))
        rules = [(pt(a, 0.12, v), pt(a, 0.98, v)) for v in (-1 + 2 * k / 8 for k in range(1, 8))]
        mz = pt(a, 0.55, 0)[2]
        depth = min(1, max(0, (mz + 5.6) / 2.6))  # figure.js: brighter nearer the eye
        leaves.append((mz, l, rim, rules, round(0.42 + 0.7 * depth, 2)))
    q = lambda c: f"{c[0]:.1f} {c[1]:.1f}"
    out = []
    for mz, l, rim, rules, op in sorted(leaves):  # far first
        lit = l < 2
        out.append(f'<path class="{"ls-g" if lit else "ls-r"}" stroke-opacity="{op:g}" d="M{q(rim[0])}L{q(rim[1])}L{q(rim[2])}L{q(rim[3])}Z"/>'
                   f'<path class="{"ls-g ls-gl" if lit else "ls-l"}" stroke-opacity="{round(op * 0.75, 2):g}" d="{"".join(f"M{q(a)}L{q(b)}" for a, b in rules)}"/>')
    w = math.ceil(xm + 6)
    return (f'<svg class="rs-still" viewBox="{-w} -100 {2 * w} 200" preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false">'
            f'{"".join(out)}</svg>')
# v2x: notes link to the instruments they describe (PAGES.md §6.4, NL-01..NL-10); targets are relative to research/
RUN = {
    "horizon": [("Watch the Council verify proposals in the swarm lab", "../index.html#lc01")],
    "weights": [("Edit a record and watch the chain fail", "../index.html#governance")],
    "lifecycle": [("The lifecycle test, trait by trait", "../lifecycles.html#test")],
    "swarm": [("See the swarm by role in the swarm lab", "../platform.html#swarm")],
    "boundary": [("Explore the eight layers and the boundary", "../platform.html#architecture")],
    "rulebook": [("Find the model layer in the architecture explorer", "../platform.html#architecture")],
    "council": [("Adjust the Council’s strictness and watch the approval rate change", "../index.html#lc01")],
    "ledger": [("Replay a ledger excerpt, then try to change the past", "../trust.html#ledger")],
    "sessions": [("See the ten sessions on the Proof page", "../evidence.html"), ("Run one simulated session on the desk", "../lifecycles.html#lc01")],
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
for _fig, (_t, _d, _h) in CAPTIONS.items():  # every quoted passage of a caption is its note's own words
    _num = next(n for n, m in META.items() if m[1] == _fig)
    _text = " ".join(t for k, t in posts[_num]["blocks"])
    for _q in re.findall(r"“(.+?)”", _d):
        assert _q in _text, f"caption {_fig}: “{_q}” is not in Post {_num}"

# r2: the series' lede on the index is note 03's (Series, part 1) own two sentences; the build stops if they change there
SERIES_LEDE = "Trust is earned in the lowest-risk lifecycle first. Then it compounds."
assert SERIES_LEDE in " ".join(t for k, t in posts[1]["blocks"]), "the §02 lede is no longer note 03's own words"

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
def hung(d): return " is-hung" if d[:1] in "“‘" else ""  # a caption that opens on a quote hangs it in the margin (research.css)
def cap_html(fig, n, cls="figcap"):
    t, d, h = CAPTIONS[fig]
    return (f'<p class="{cls}"><span class="figcap-n">Fig.{NB}{n}</span><span class="figcap-t">{H.escape(t, quote=False)}</span>'
            f'<span class="figcap-d{hung(d)}">{H.escape(d, quote=False)}</span><span class="figcap-h">{H.escape(h, quote=False)}</span></p>')

# ---------------- templates from the live homepage ----------------
index_html = read(os.path.join(ROOT, "index.html"))
NAV = re.search(r'  <header class="nav">.*?</header>\n  <div class="nav-menu">.*?\n  </div>\n', index_html, re.S).group(0)
FOOTER = re.search(r'  <footer class="footer">.*?</footer>\n', index_html, re.S).group(0)
# the Lifecycle 01 sessions: ONE record (#oxa-sessions, on the home and Proof pages) that the chart and every session count
# are drawn from. The 'sessions' figure (note 09) reads each column's NAV regime from it: data-regimes on its stage, one
# letter per session (p = premium, d = discount), so the note carries no second copy of the record. Its ten columns are
# drawn for ten sessions: a record with another count needs that figure and the note looked at, so the build stops.
SESSIONS = json.loads(re.search(r'<script type="application/json" id="oxa-sessions">(.*?)</script>', index_html, re.S).group(1))["sessions"]
REGIMES = "".join({"prem": "p", "disc": "d"}.get(str(x.get("regime", "")).strip().lower()[:4], "?") for x in SESSIONS)
assert len(REGIMES) == 10 and set(REGIMES) <= {"p", "d"}, f"#oxa-sessions: note 09's figure draws ten sessions, each premium or discount; the record gives {REGIMES!r}"
def stage_data(fig): return f' data-regimes="{REGIMES}"' if fig == "sessions" else ""
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

def chrome(prefix, current):
    nav = NAV.replace('href="', f'href="{prefix}').replace(f'href="{prefix}#', 'href="#')
    nav = nav.replace(f'<a href="{prefix}research.html">Research</a>', f'<a href="{prefix}research.html" aria-current="page">Research</a>') if current == "research" else nav
    foot = FOOTER.replace('href="', f'href="{prefix}').replace(f'href="{prefix}http', 'href="http').replace(f'href="{prefix}mailto', 'href="mailto')
    return nav, foot

def og(prefix, url, title, desc):
    return f'''  <meta name="description" content="{H.escape(desc, quote=True)}">
  <meta name="theme-color" content="#0E1512">
  <link rel="canonical" href="{url}">
  <meta property="og:url" content="{url}">
  <meta property="og:site_name" content="OpenEXA">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{H.escape(title, quote=True)}">
  <meta property="og:description" content="{H.escape(desc, quote=True)}">
  <meta property="og:image" content="{og_image(url)}">
  <meta property="og:image:alt" content="{H.escape(title, quote=True)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{H.escape(title, quote=True)}">
  <meta name="twitter:description" content="{H.escape(desc, quote=True)}">
  <meta name="twitter:image" content="{og_image(url)}">
  {ROBOTS}
  {FEED_LINKS[0]}
  {FEED_LINKS[1]}
{HEAD_LINKS.format(p=prefix)}'''

# ---------------- articles ----------------
ordered = [posts[n] for n in ORDER]
for i, post in enumerate(ordered):
    slug, fig, label, dek_short = META[post["num"]]
    post.update({"slug": slug, "fig": fig, "label": label, "short": dek_short, "order": i + 1, "file": f"research/{i + 1:02d}-{slug}.html"})

def pager_card(p, k, cls=""):
    return (f"<a class='pager-card{cls}' href='{os.path.basename(p['file'])}'><span class='k'>{k}</span>"
            f"<h3>{title_html(p['title'])}</h3><p>{inline(p['short'])}</p></a>")

for i, post in enumerate(ordered):
    prev = ordered[i - 1] if i else None
    nxt = ordered[i + 1] if i + 1 < len(ordered) else None
    nav, foot = chrome("../", "research")
    heads = [(slugify(t), t) for k, t in post["blocks"] if k == "h"]
    # the link is a grid (numeral, words): the words are one span, so a no-break compound inside them is not a grid item
    toc = "".join(f'<li><a href="#{a}"><span>{inline(t)}</span></a></li>' for a, t in heads)
    body = []
    first_p = True
    for k, t in post["blocks"]:
        if k == "h": body.append(f'<h2 id="{slugify(t)}">{disp(t)}</h2>')  # r5: bound as the titles are (disp)
        else:
            body.append(f'<p{" class=\"lead\"" if first_p else ""}>{inline(t)}</p>'); first_p = False
    dek = post["dek"] or post["short"]
    title = post["title"]
    url = f"https://www.openexa.com/{post['file']}"
    n = f"{post['order']:02d}"
    run = "".join(f'<li><a class="link-arrow" href="{href}">{H.escape(text, quote=False)}{NB}{ARROW}</a></li>' for text, href in RUN[post["fig"]])
    long_title = len(re.sub(r" A Research Note on .+$", "", title)) > 52
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{H.escape(title)} — OpenEXA Research</title>
{og("../", url, title + " — OpenEXA Research", dek)}
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
      <div class="figure-stage article-figure" data-figure="{post['fig']}"{stage_data(post['fig'])} data-spin="0.10" data-plate data-rest="2.5" aria-hidden="true"><canvas></canvas>{labels_html(post['fig'])}</div>
      <div class="container">
        <div class="article-hero-grid">
          <div>
            <div class="eyebrow" data-reveal><span><span class="nw">Research · Note{NB}{n} of{NB}{len(ordered):02d} ·</span> <span class="nw">{H.escape(kind(post))}</span></span></div>
            <h1 class="display-1 article-title{' article-title--long' if long_title else ''}{' article-title--split' if 't-head' in title_html(title) else ''}" data-reveal data-split style="--d:60ms">{title_html(title)}</h1>
            <p class="lede mt-3" data-reveal style="--d:120ms">{inline(dek)}</p>
            <div class="article-meta" data-reveal style="--d:180ms"><span>Founder’s notes</span><span>{post['minutes']}{NB}min read</span></div>
          </div>
          {cap_html(post['fig'], n, "figcap article-figcap")}
        </div>
      </div>
    </section>

    <section class="section article-body-section">
      <div class="container">
        <div class="grid">
          <nav class="col-3 article-side" aria-label="In this note">
            <div class="sticky">
              <div class="eyebrow mb-2">In this note</div>
              <ol class="toc" data-toc>{toc}</ol>
              <div class="article-share mt-3"><a class="link-arrow" href="../research.html">All research {ARROW}</a></div>
            </div>
          </nav>
          <article class="col-7 offset-5 article">
            {"".join(body)}
            <div class="article-end"><span class="mark" aria-hidden="true"></span><span>OpenEXA Research · Founder’s notes · {n}{NB}/{NB}{len(ordered):02d}</span></div>
            <div class="note-run"><p class="note-k">See it run</p><ul>{run}</ul></div>
            <div class="note-disc"><p class="note-k">Series disclosure</p><p>{H.escape(SERIES_DISCLOSURE, quote=False)}</p><p><a href="#disclosures">See the disclosures.</a></p></div>
          </article>
        </div>
      </div>
    </section>

    <section class="section is-paper-2 section--tight">
      <div class="container">
        <div class="pager">
          {pager_card(prev, f"← Previous · {prev['order']:02d}") if prev else "<a class='pager-card' href='../research.html'><span class='k'>← Research</span><h3>All ten notes</h3><p>The research behind swarm-based agentic lifecycles, in reading order.</p></a>"}
          {pager_card(nxt, f"Next · {nxt['order']:02d} →", " next") if nxt else "<a class='pager-card next' href='../access.html'><span class='k'>Next →</span><h3>Bring us a lifecycle.</h3><p>For institutions running high-value lifecycles and partners building on agentic infrastructure.</p></a>"}
        </div>
      </div>
    </section>
  </main>

{foot}
  <script src="../assets/js/figure.js" defer></script>
  <script src="../assets/js/site.js" defer></script>
  <script src="../assets/js/research.js" defer></script>
</body>
</html>
'''
    write(os.path.join(ROOT, post["file"].replace("/", os.sep)), page)
    print("wrote", post["file"], f"({post['minutes']} min)")

# ---------------- index ----------------
nav, foot = chrome("", "research")
rows = []
for post in ordered:
    t, d, h = CAPTIONS[post["fig"]]
    cap = " ".join(f'data-cap-{k}="{H.escape(v, quote=True)}"' for k, v in (("n", f"Fig.{NB}{post['order']:02d}"), ("t", t), ("d", d), ("h", h)))
    rows.append(f'''          <li class="post" data-figure-target="{post['fig']}" data-figure-stage="research-figure" {cap}>
            <a href="{post['file']}">
              <span class="post-n">{post['order']:02d}</span>
              <div class="post-main">
                <h3>{title_html(post['title'])}</h3>
                <p>{inline(post['short'])}</p>
              </div>
              <div class="post-meta"><span>{post['minutes']}{NB}min</span>{ARROW}</div>
            </a>
          </li>''')
notes = [p for p in ordered if p["label"] == "Research note"]
url = "https://www.openexa.com/research.html"
# r2: the share title is the <title>, as launch_meta_v9.py writes it, so research.html no longer differs between the
# research build and the chain's last step (r1 open issue: built alone it said "Research — OpenEXA")
INDEX_TITLE = "Research — OpenEXA · The thinking behind agentic lifecycles"
# r4 (r4-copy): "the Execution Council" is a name (VOICE 5.9); §03's link reads "Start with the Gen-AI series" (no
# capital article mid-sentence, no colon subtitle inside a link)
desc ="Ten notes on the research behind swarm-based agentic lifecycles: compounding error and decomposition, post-training a model to a rulebook, the Execution Council, the hash-chained ledger, and ten sessions on real capital."
index_page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{INDEX_TITLE}</title>
{og("", url, INDEX_TITLE, desc).replace('content="article"', 'content="website"')}
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
    <section class="page-hero page-hero--dark is-dark grain research-hero">
      <div class="figure-stage research-figure has-still" id="research-library" data-figure="library" data-spin="0.08" data-plate data-rest="2.5" aria-hidden="true">{library_still()}<canvas></canvas>{labels_html("library")}</div>
      <div class="container">
        <div class="grid">
          <div class="col-7">
            <div class="eyebrow" data-reveal>Research · Founder’s notes</div>
            <h1 class="display-1" data-reveal data-split style="--d:60ms">The thinking behind the swarm.</h1>
            <p class="lede mt-3" data-reveal style="--d:120ms">Ten notes on why high-stakes work should be run by thousands of narrow agents behind one deterministic boundary, from the mathematics of compounding error to what ten sessions on real capital taught us.</p>
            <div class="article-meta" data-reveal style="--d:180ms"><span>{len(ordered)} notes</span><span>{sum(p['minutes'] for p in ordered)}{NB}min in total</span><span>Two research notes · an eight-part series</span></div>
          </div>
          <p class="figure-cap hp-cap rs-herocap"><span class="fc-t"><b class="fc-n">Plate</b><span class="fc-d"> · </span>{LIBRARY_CAPTION[0]}</span><span class="fc-h">{LIBRARY_CAPTION[1]}</span></p>
        </div>
      </div>
    </section>

    <!-- v2x: the shelf. The ten notes, and beside them (pinned below them on phones) one plate that shows the figure of
         the note pointed at, focused or, on touch screens, read: research.js. Without JavaScript the plate is not drawn
         and the list takes the full width (research.css, @media (scripting: none)). -->
    <div class="rs-shelf">
      <section class="section" id="notes">
        <div class="container">
          <div class="rs-col">
            <div class="sec-head" data-reveal role="heading" aria-level="2"><span class="idx">01</span><span class="lab">Research notes</span><span class="aside">Start here · the argument from first principles</span></div>
            <ol class="posts-list" data-reveal>
{chr(10).join(rows[:2])}
            </ol>
          </div>
        </div>
      </section>

      <!-- r2 (r2-fidelity): 01 and 02 share one ground, so the pinned plate beside them never crosses a band's edge; the
           chapter head and its rule mark the change. The paper-2 band moves to 03, so the grounds still alternate -->
      <section class="section" id="series">
        <div class="container">
          <div class="rs-col">
            <div class="sec-head" data-reveal><span class="idx">02</span><span class="lab">The series</span><span class="aside">Eight notes · the system, gate by gate</span></div>
            <div class="rs-intro">
              <h2 class="display-2" data-reveal data-split>{PH("From the unit of work", "to the open platform.")}</h2>
              <p class="body-lg" data-reveal style="--d:80ms">{SERIES_LEDE.replace("lowest-risk", '<span class="nw">lowest-risk</span>')} These eight notes describe how.</p>
            </div>
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
            <figcaption class="rs-caption">
              <p class="rs-hint"><span class="rs-hint-p">Point at a note and the figure becomes its idea.</span><span class="rs-hint-t">Scroll the list and the figure follows the note you are on.</span></p>
              {cap_html(ordered[0]['fig'], '01', 'figcap rs-cap')}
            </figcaption>
          </figure>
        </div>
      </div>
    </div>

    <section class="section is-paper-2" id="blog">
      <div class="container">
        <div class="sec-head" data-reveal><span class="idx">03</span><span class="lab">The blog</span><span class="aside">{BLOG['total']} posts · {BLOG['years'][0]}–{BLOG['years'][1]}</span></div>
        <div class="grid t-2 mb-3">
          <div class="col-6"><h2 class="display-2" data-reveal data-split>{PH("Three collections,", "from market structure", "to AI agents.")}</h2></div>
          <div class="col-5 offset-7"><p class="body-lg" data-reveal style="--d:80ms">Research summaries, market-structure economics and the first notes on AI agents in finance, from the people behind OpenEXA and the researchers they work with.</p><a class="link-arrow mt-3 scholar-link" href="{SCHOLAR}" target="_blank" rel="noopener">The papers on Google Scholar {OUTB}</a></div>
        </div>
        <div class="card-grid card-grid--{len(BLOG['collections'])}" data-reveal style="--d:120ms">
{chr(10).join(f'          <a class="card research-card" href="blog/index.html#{c["key"]}"><div class="n"><span>{c["count"]} posts</span><span>{c["years"][0] if c["years"][0] == c["years"][1] else str(c["years"][0]) + "–" + str(c["years"][1])}</span></div><h3 class="h4">{H.escape(c["label"])}</h3><p>{H.escape(us(c["lede"]))}</p><span class="link-arrow mt-3">Browse the collection{NB}{ARROW}</span></a>' for c in BLOG['collections'])}
        </div>
        <div class="mt-4 row-links" data-reveal><a class="link-arrow" href="blog/index.html#series">Start with {re.sub(r"^The ", "the ", BLOG['series']['name'])} {ARROW}</a><a class="link-arrow" href="blog/index.html">All {BLOG['total']} posts {ARROW}</a></div>
      </div>
    </section>

    <section class="section" id="principles">
      <div class="container">
        <div class="sec-head" data-reveal><span class="idx">04</span><span class="lab">Four constants</span><span class="aside">What never changes</span></div>
        <div class="grid t-2">
          <div class="col-5"><h2 class="display-2" data-reveal data-split>{bind("The research contribution is four constants.")}</h2></div>
          <div class="col-6 offset-7">
            <ol class="num-list" data-reveal style="--d:80ms">
              <li><h3>Agents decide. Code executes.</h3><p>The top four layers estimate and reason; the bottom four are deterministic. The boundary between them is a typed schema.</p></li>
              <li><h3>No single agent sees the whole job.</h3><p>Each agent is scoped to one gate and does one thing. Its failure is local and its output is a proposal until something downstream permits it.</p></li>
              <li><h3>Nothing an agent believes can move what it is not permitted to.</h3><p>Capabilities are held per agent and per tool, enforced by the runtime rather than by the model’s good behavior.</p></li>
              <li><h3>Anything that settles is written to a ledger nobody can edit.</h3><p>Append-only, hash-chained, replayable{NB}— and written only after an independent counterparty confirms.</p></li>
            </ol>
          </div>
        </div>
      </div>
    </section>

    <section class="cta-band is-dark grain">
      <i class="mark globe" aria-hidden="true"></i>
      <div class="container">
        <div class="eyebrow" data-reveal>See it run</div>
        <h2 class="display-2 mt-2" data-reveal data-split style="--d:60ms">Three of these ideas run in your browser.</h2>
        <p class="lede mt-3" data-reveal style="--d:120ms">Tighten the Council in the swarm lab. Edit a record and watch the chain break. Run one simulated session of Lifecycle{NB}01.</p>
        <div class="row" data-reveal style="--d:180ms">
          <a class="btn" href="index.html#lc01">Open the swarm lab {ARROW}</a>
          <a class="btn btn--ghost" href="index.html#governance">Break the chain</a>
          <a class="btn btn--ghost" href="lifecycles.html#lc01">Run the desk</a>
        </div>
      </div>
    </section>
  </main>

{foot}
  <script src="assets/js/figure.js" defer></script>
  <script src="assets/js/site.js" defer></script>
  <script src="assets/js/research.js" defer></script>
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
