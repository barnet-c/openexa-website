"""Rebuild the Company page's team section (03) from the old openexa.com About page (/status/), in the site's own design.

Source: oldteam/team.json + portraits, scraped from https://www.openexa.com/status/ (2026-09-29).
Changes from the source, deliberately:
  - Barnet Sherman removed (now a customer).
  - Ajit: no patent count (his request); his short line is the current AI-company one.
  - Titles for the five people already on the site keep their current C-level titles; everyone else uses the About page's.
  - Sentences describing OpenEXA's former crypto business as someone's current work are dropped (Victor, Abhishek,
    Shalabh); career facts are kept as written (Tim's research areas, Mike's systems work, Sreeram's lab).
  - Julius's short line drops "Crypto" from "AML & Crypto Risk"; John's surname follows his bio and LinkedIn (Schuster).
  - 2026-10-02: John Schuster, Subuddh Parekh, Abhishek Sinha, Dr. Julius E. Ekeroma and Dipit Nanawati moved from the
    team to the advisors (Ajit's request). The team is the five leaders; the advisors are eight.
  - 2026-10-27: three typos in the scraped bios are corrected (FIX), and Philip's link, labelled "LinkedIn" on the old
    About page, is his UW faculty page, so it reads "Faculty page".
  - 2026-10-28: the stats are plain final values (no data-count: no number is ever shown counting up), the X link reads
    "X (Twitter)", and generic link labels carry the person's name for screen readers, so every link name is unique.
  - 2026-10-30: Subuddh Parekh moved from the team to the advisors (owner's request). He is the last advisor (A-09),
    same bio and portrait, kicker "Advisor · AI & ML". The team is four; the advisors are nine (the counts and the
    sentence above the register are computed from the two lists).
  - 2026-10-30 (v2x): the section is an edited register, not a grid of cards. One row per person: register code,
    portrait, name, kicker, the card line, the bio behind "Read the full bio", then links. Grammar-level fixes only in the
    bios (FIX: a subject for the fragments, one comma splice, curly apostrophes); every claim keeps its words. One
    portrait treatment for all thirteen (portrait()): the head is measured and set at one size and height, the tones
    are normalised and printed ink on paper, so photos from different cameras sit together. New file names
    (<slug>-v2x.webp); the old files stayed for pages cached before the change, and went a day after the live site
    switched to the new ones (published 2 Nov 2026; deleted 4 Nov, integrate award budgets).
  - 2026-10-31 (lab company-editorial, ported in r1): the card line keeps hyphenated compounds whole (span.nowrap, the
    site's utility), so a two-line line never breaks at "capital-|markets"; words unchanged.
  - 2026-10-31 (v2x r1): one portrait, set closer (the head is 40% of the frame's width, its top 11% down, so the eyes
    sit on one line about a third down and faces read at 64-96 px); Mike's snapshot no longer zoomed past the others
    (TUNE k 1.0). Each master is also written at 160 and 320 px (<slug>-v2x-160.webp, -320.webp) and the img carries a
    srcset, so a phone fetches a 64 px portrait's worth, not 560 px (Company was ~1.0 MB on a phone).
  - 2026-10-31 (v2x r2, copy): two card lines say what their bios say. Philip Bond's reads his title as his bio gives it
    ("Edward E. Carlson Distinguished Professor in Business Administration", Foster School, UW; the old line read as a
    title he does not hold, C-178); Abhishek Sinha's drops "on the ground" and writes "V1" as his bio does, with the
    bio's Amazon and Microsoft (C-181). No new fact.
  - 2026-10-31 (v2x r3, copy): "Eigen Layer" is written as the project writes its name, "EigenLayer" (Sreeram Kannan's
    card line and bio; a typo-level fix, FIX). No other word changes.
  - 2026-10-31 (v2x r4, art): an internal link ("His research on the blog") ends in the site's drawn svg.arr, as every
    other internal text link does, not a text arrow (U+2192); external links keep their "↗". Words unchanged.
  - 2026-11-01 (cut, the owner's word budget: "so many words everywhere"): the register says less and the bios stay, in
    the people's own words, behind their expanders. Gone: the register codes (T-01, A-01 ...), the section row, the
    first sentence above the figures (the figures 4 and 9 say it) and its closing clause ("with deep experience in AI,
    capital markets and financial innovation"), the advisors' paragraph and the advisors' card lines (their kickers
    name each one's area; the rest is in the bio). The four team members keep their card line. The expander reads
    "Bio" (+ / x), with the person's name for screen readers. The section is named for the bar's chapter list by
    data-chapter (02: §01 Mission left the page). Every bio, name, kicker, link and portrait is unchanged.
  - 2026-11-01 (award a2, 4K): the portraits' sizes attribute follows the page above 1920 px (5vw = 6rem there) and
    the advisors carry their own, smaller sizes (SIZES_ADV), so no portrait is upscaled at 3840 and no advisor fetches
    twice the pixels it shows. Markup otherwise unchanged.
  - 2026-11-03 (award a4, design jury): on wide screens company.css sets the advisors as two ruled columns that read
    down; the list carries its row count (--rows, half the advisors, rounded up) so the columns follow the roster.
    Words, order and markup otherwise unchanged.
  - 2026-11-06 (hill climb hc4, design director: "the team rows read as two unrelated columns"): from 1200 px the team
    takes the advisors' form, two ruled columns reading down, so the team list carries its row count too (--rows, half
    the team, rounded up). Words, order and markup otherwise unchanged.
  - 2026-11-06 (hill climb hc5, one chapter-head pattern; system's request): the section's head is the site's chapter
    head (.ch-head.ch-spread: the heading, its line under it, the three figures as the spread's key), not a heading
    with its line top right; each firm in the line is kept whole (no-break spaces). Words unchanged.
  - 2026-11-07 (hill climb hc15, design director 4.3: the page ended in 1,441 px of unbroken ink): "How we build" moved
    between the story and the team, so the page alternates dark, paper-2, dark, paper, then the dark close, and reads
    why, how, who, act. The team is chapter 03 (data-n), and the section this script writes ends at its own marker,
    <!-- /THE TEAM -->, right after it (it ran to <!-- 04 FOUR CONSTANTS -->). Words, order and markup otherwise unchanged.
  - 2026-11-08 (hill climb hc19, design director 4.6): the line under the head keeps "at Google" together (a no-break
    space), so it never ends a line on "at" (it did at 1440 and 1920). The four card lines take the same care (tie():
    a short word is tied to the word after it, so "90% of / Microsoft's" and "Director of /
    Computational" no longer happen at any width, and a short last pair stays together, so no line ends on one word
    alone). Words unchanged.
  - 2026-11-08 (hill climb hc20, design director 4.2: "the last stock idiom on a main page"): the head is "Systems people
    and market people." ("under one roof" cut, 3 words); the line under it names the firms. company.css sets this one
    head on one line wherever it fits, as Platform's "Every action passes three gates." (it is 25ch, the chapter
    heads' measure is 22ch).
  - 2026-11-09 (hill climb hc29, design director: "one grade for all 13 portraits"; the owner's 8 Nov freedom allows one
    consistent treatment): each portrait is set on the face, not the silhouette (hand-measured eye line, centre line and
    face height per source, FACE): the eyes 40 % down the circle, the face 30 % of it (the head about 62 %), centred;
    the cheeks' mid-tone pulled toward L* 55 (35 % of each face's own difference kept), blacks and whites held at
    L* 14 / 93. Mike Lockhart's snapshot keeps his eyes at 50 % (the photo ends under his shoulders). New file names
    (<slug>-g2-v2x.webp and its 160 / 320 twins); the -v2x files stay for pages cached before the change and can go a
    day after the live site switches. No one is swapped or retouched; words and markup otherwise unchanged.
  - 2026-11-10 (hill climb hc30r, RETHINK-hc30 COMP-1): this script also draws the hero's still, the sheet of 96 agents
    the page shows without JavaScript (hero_still(), written between <!-- THE STILL --> and <!-- /THE STILL -->). It
    reads the agents from the AGENTS literal in site/assets/js/company-hero.js, the one place they are defined, so the
    still and the live figure cannot drift; it fails if the literal is missing or its marks do not fill the disc.
  - 2026-11-11 (hill climb hc31r, LEAP-hc31 COMP-1): with scripts and motion the sheet is lit by the run (company-hero.js:
    an agent is green for 300 ms when it proposes), so an agent's bit 15 is now read only here, for the still without
    JavaScript, and by company-hero.js under reduced motion: the still stays twelve agents green. Nothing this script
    writes changed.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import html as H, io, json, math, re, shutil
from pathlib import Path
from PIL import Image, ImageFilter, ImageOps

FILES = Path(str(DATA))
SRC = FILES / "oldteam"
V1 = Path(str(DATA / 'v1-team'))
ROOT = Path(str(SITE))
IMGDIR = ROOT / "assets" / "img" / "team"
SCHOLAR = "https://scholar.google.com/citations?user=P40aOHIAAAAJ"
old = {p["name"]: p for p in json.load(open(SRC / "team.json", encoding="utf-8"))}

DROP = [  # sentences removed from bios (old crypto-business positioning)
    "At OpenEXA, Victor is busy designing the business workflow for the movement of real world assets into crypto markets.",
    "Abhishek believes in OpenEXA as a startup.", "He believes it would solve the institutional trust problem in crypto.",
    "Currently, Shalabh is passionate about pursuing the field of AI Crypto, where he aims to bridge traditional Wall Street assets into crypto markets.",
    "Shalabh is uniquely positioned to explore innovative ways of integrating AI with crypto.",
    "His ultimate goal is to help drive the mainstream adoption of crypto by leveraging the power of AI and Blockchain.",
]
FIX = [  # typos in the scraped bios
    ("reuses state capital", "reuses staked capital"), ("to reduces", "to reduce"), ("from the Caltech", "from Caltech"),
    # v2x (30 Oct): grammar only. Fragments get their subject, one comma splice becomes two sentences; no claim changes.
    ("Class of 2019, he has contributed", "Class of 2019. He has contributed"),
    ("Mike, a seasoned software architect", "Mike is a seasoned software architect"),
    ("Graduated from Stanford University with Bachelor of Science in Computer Science and Master of Science in Computer Science.",
     "He graduated from Stanford University with a Bachelor of Science and a Master of Science in Computer Science."),
    ("A blockchain technology enthusiast with", "Abhishek is a blockchain technology enthusiast with"),
    ("in the field. Has experience in", "in the field. He has experience in"),
    ("value. Extensive expertise in", "value. He has extensive expertise in"),
    ("experience. Proven ability to", "experience. He has a proven ability to"),
    ("credibility. Recognized for", "credibility. He is recognized for"),
    ("decisiveness. Strengths include", "decisiveness. His strengths include"),
    ("to get most out of them", "to get the most out of them"),
    ("Eigen Layer", "EigenLayer"),  # v2x r3: the project's own spelling (Sreeram Kannan's bio)
    ("An expert in compliance and financial risk with", "Julius is an expert in compliance and financial risk with"),
    ("Ph.D. in Business Analytics, expert in", "He holds a Ph.D. in Business Analytics and is an expert in"),
    ("and trade surveillance. Integrating data sets, performing analytical calculations, building and configuring models, performing model validation and tuning.",
     "and trade surveillance. His work includes integrating data sets, performing analytical calculations, building and configuring models, and performing model validation and tuning."),
]
def curly(s):  # typography: apostrophes as U+2019 (VOICE §7); no quotation marks occur in these texts
    return s.replace("'", "’")
def whole(s):  # 2026-10-31 (lab company-editorial): a card line never breaks inside a hyphenated compound ("capital-|markets")
    return re.sub(r"\w+(?:-\w+)+", lambda m: f'<span class="nowrap">{m.group(0)}</span>', s)
WEAK = r"(?:a|an|and|as|at|by|for|from|in|its|of|on|or|the|to|with|&amp;)"
def tie(s):  # 2026-11-08 (hc19): a card line never ends a line on a short word ("90% of / Microsoft's"),
    s = re.sub(rf"(?<![\w;])({WEAK}) (?=\S)", r"\1&nbsp;", s, flags=re.I)  # and never ends on one word alone
    s = s.replace("Big Tech", "Big&nbsp;Tech")  # a name, never "Big / Tech"
    head, _, last = s.rpartition(" ")
    unit = (head.rpartition(" ")[2] + " " + last).replace("&nbsp;", " ").replace("&amp;", "&")
    return f"{head}&nbsp;{last}" if head and len(unit) <= 24 else s  # 24: a longer tied unit leaves a short line above it on a phone
# (slug, display name, source name, title, short line, v1 photo or None, extra links)
TEAM = [
    ("ajit-dubey", "Ajit K Dubey", "Ajit K Dubey", "Founder · CEO", "Founder and CEO of OpenEXA. Big Tech and capital-markets veteran, building the foundational infrastructure for agentic lifecycles.", "ajit-dubey", []),
    ("tim-leung", "Dr. Tim Leung", "Tim Leung, Ph.D.", "Chief Scientist", "Boeing Endowed Chair Professor of Applied Mathematics and Director of Computational Finance & Risk Management at the University of Washington.", "tim-leung", [("Google Scholar", SCHOLAR)]),
    ("mike-lockhart", "Mike Lockhart", "Mike Lockhart", "Chief Technology", "Architect of high-stakes systems, including those that touch 90% of Microsoft's revenue.", "mike-lockhart", []),
    ("shalabh-choudhri", "Shalabh Choudhri", "Shalabh Choudhri", "Chief AI Agents", "Leads agent research and the post-trained models behind OpenEXA's domain-specific execution agents.", "shalabh-choudhri", []),
]
# Nine advisors: the three long-standing ones, then four who moved over from the team on 2026-10-02 (John Schuster,
# Abhishek Sinha, Dr. Julius E. Ekeroma, Dipit Nanawati) and Victor Gamolsky, who swapped places with Subuddh Parekh later
# that day (Victor takes Subuddh's slot as an advisor; Subuddh takes Victor's slot on the team). Kickers read
# "Advisor · <area>", the area taken from each person's own bio or old About-page label ("Strategy & Tech" for Victor), so
# no advisor card carries an employee title (Program Manager, Chief Compliance, Chief Product).
# 2026-10-30: Subuddh Parekh moved from the team to the advisors (owner's request): the last advisor, A-09, "Advisor · AI & ML".
ADVISORS = [
    ("kumar-mehta", "Kumar Mehta", "Kumar Mehta", "Advisor · Networking", "Co-founder and CDO, and former CEO, of Versa Networks.", None, []),
    ("sreeram-kannan", "Sreeram Kannan", "Sreeram Kannan", "Advisor · Blockchain Systems", "Founder and CEO of EigenLayer and director of the University of Washington's Blockchain Lab.", None, []),
    ("philip-bond", "Dr. Philip Bond", "Philip Bond, Ph.D.", "Advisor · Capital Markets", "Edward E. Carlson Distinguished Professor in Business Administration at the Foster School of Business, University of Washington.", None, [("His research on the blog", "blog/index.html#economics")]),
    ("john-schuster", "John Schuster", "John Shuster", "Advisor · Strategy & Markets", "A startup founder and executive, with an MBA in Finance from The Wharton School.", None, []),
    ("victor-gamolsky", "Victor Gamolsky", "Victor Gamolsky", "Advisor · Strategy & Technology", "A decade of building and scaling ventures with lean, evidence-driven product methods.", "victor-gamolsky", []),
    ("abhishek-sinha", "Abhishek Sinha", "Abhishek Sinha", "Advisor · Technology Programs", "Over a decade delivering V1 initiatives, with experience in large technology companies such as Amazon and Microsoft.", None, []),
    ("julius-ekeroma", "Dr. Julius E. Ekeroma", "Dr. Julius E. Ekeroma, Ph.D.", "Advisor · Compliance & Risk", "Expert in compliance and financial risk, with 25+ years in auditing, operations and financial forensics.", None, []),
    ("dipit-nanawati", "Dipit Nanawati", "Dipit Nanawati", "Advisor · Financial Markets", "A trusted advisor to some of Wall Street's largest firms on operational efficiency, compliance and profitability.", None, []),
    ("subuddh-parekh", "Subuddh Parekh", "Subuddh Parekh", "Advisor · AI & ML", "Engineering, product and machine-learning expert, with a BS and MS in Computer Science from Stanford.", None, []),
]

# ---------------- portraits: one treatment for all thirteen ----------------
# The sources are cut-outs from different cameras, crops and exposures. hc29 (9 Nov 2026, the design director: "one grade
# for all 13 portraits"): each is set on its face, not on its silhouette. FACE holds three hand measurements per source
# (in the chosen source file's pixels): the face's centre line, its eye line and its height (eyes to chin, or what that
# height would be where the head is tipped or turned: Mike looks down, John is in profile, Subuddh's selfie widens his
# eyes). The face is scaled to FACE_H of the frame (so the head, crown to chin, is about 62 %) with the eyes EYE_Y down
# and the centre line in the middle; a side where the photo itself was cut through the head stays outside the frame; the
# body always reaches the bottom edge (the scale grows just enough where it would not). Tones: the subject stretched
# (1st-99.5th percentile), its cheeks' mid-tone pulled toward L* LT (PULL keeps that share of each face's own difference,
# so no complexion is flattened into another's), black and white held at L* LB and LW (no crushed blacks), then printed
# ink (#0E1512) on paper (#F5F2EC). Never retouched: one curve, one crop and one sharpening per photo.
# TUNE: Mike's only photo is a small holiday snapshot zoomed in, cut just under his shoulders (his eyes sit at .50 so the
# body still reaches the edge without a larger face; half the stretch, softened, since its noise is not detail).
SIZE, EYE_Y, FACE_H = 560, 0.40, 0.30
LT, PULL, LB, LW = 55, 0.35, 14, 93
INK, PAPER, MID = (14, 21, 18), (245, 242, 236), (112, 112, 104)
FACE = {  # source pixels (centre x, eye y, face height), measured on each person's chosen source (hc29)
    "Ajit K Dubey": (245, 177, 124), "Tim Leung, Ph.D.": (158, 150, 114.5), "Mike Lockhart": (223, 240.5, 120),
    "Shalabh Choudhri": (523, 375, 326), "Kumar Mehta": (134, 103.7, 92.8), "Sreeram Kannan": (99, 102, 76.3),
    "Philip Bond, Ph.D.": (152.4, 77.2, 47), "John Shuster": (143.5, 133.7, 77.5), "Victor Gamolsky": (200, 112.8, 96.6),
    "Abhishek Sinha": (97, 69.8, 57.8), "Dr. Julius E. Ekeroma, Ph.D.": (595, 331, 246), "Dipit Nanawati": (541, 431, 298),
    "Subuddh Parekh": (475, 681, 266),
}
TUNE = {"Mike Lockhart": dict(eye=0.50, soft=True)}
STEM = "{}-g2-v2x"  # hc29: new names for the new grade (team images are cached for a day)
SMALL = (160, 320)
# company.css: the team's portraits are 96 / 80 / 64 px, the advisors' 64 / 56 / 48 px; above 1920 px the page grows
# with the window (site.css: root 100vw / 120), so 6rem is 5vw and 4rem 3.34vw there (award a2: rem inside sizes is
# 16 px, so at 3840 the team got the 160w file for a 192 px circle). Each list says its own size, so an advisor on a
# 2x laptop or a 3x phone takes the 160w file (it took the 320w).
SIZES = "(max-width: 600px) 64px, (max-width: 1024px) 80px, (min-width: 1921px) 5vw, 96px"
SIZES_ADV = "(max-width: 600px) 48px, (max-width: 960px) 56px, (min-width: 1921px) 3.34vw, 64px"
def subject(path):
    im = Image.open(path).convert("RGBA"); box = im.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
    return im, box
def cut_sides(im, box):
    a = im.getchannel("A"); W, _ = im.size; x0, y0, x1, y1 = box; px = a.load(); upper = range(y0, y0 + (y1 - y0) // 2)
    return (x0 == 0 and sum(1 for y in upper if px[0, y] > 128) > 8, x1 == W and sum(1 for y in upper if px[W - 1, y] > 128) > 8)
def _lstar(c):
    c = [v / 255 for v in c]; c = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in c]
    y = .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
    return 116 * y ** (1 / 3) - 16 if y > 216 / 24389 else y * 24389 / 27
_RAMP = ImageOps.colorize(Image.frombytes("L", (256, 1), bytes(range(256))), INK, PAPER, mid=MID)
LSTAR = [_lstar(_RAMP.getpixel((g, 0))) for g in range(256)]  # the L* each grey prints at
def grey_for(L): return min(range(256), key=lambda g: abs(LSTAR[g] - L))
def portrait(slug, src_name, v1_name):
    cands = [SRC / Path(old[src_name]["img"]).name]
    if v1_name: cands.append(V1 / f"{v1_name}.png")
    best = max(cands, key=lambda c: subject(c)[1][3] - subject(c)[1][1])  # the tallest subject = most real pixels
    im, box = subject(best); cut_l, cut_r = cut_sides(im, box); t = TUNE.get(src_name, {}); cx, ey, fh = FACE[src_name]
    eye = SIZE * t.get("eye", EYE_Y); s = max(SIZE * FACE_H / fh, (SIZE - eye) / (box[3] - ey))
    x, y = SIZE / 2 - cx * s, eye - ey * s
    if cut_l: x = min(x, -box[0] * s)
    if cut_r: x = max(x, SIZE - box[2] * s)
    big = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS); x, y = round(x), round(y)
    big = big.crop((max(0, -x), max(0, -y), big.width, big.height))
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0)); canvas.alpha_composite(big, (max(0, x), max(0, y)))
    alpha = canvas.getchannel("A"); g = canvas.convert("RGB").convert("L")
    on = sorted(v for v, al in zip(g.tobytes(), alpha.tobytes()) if al > 160); lo, hi = on[int(len(on) * .01)], on[int(len(on) * .995)]
    q = .55 if t.get("soft") else 1.0
    g = g.point(lambda v: max(0, min(255, round(v + q * ((v - lo) * 255 / max(1, hi - lo) - v)))))
    ec = fh * s; cheeks = (round(SIZE / 2 - .45 * ec), round(eye + .15 * ec), round(SIZE / 2 + .45 * ec), round(eye + .75 * ec))
    cv = sorted(v for v, al in zip(g.crop(cheeks).tobytes(), alpha.crop(cheeks).tobytes()) if al > 160)
    gb, gw = grey_for(LB), grey_for(LW); fm = max(8, min(247, cv[len(cv) // 2]))
    own = LSTAR[round(gb + (gw - gb) * fm / 255)]  # the cheeks as the stretch alone would print them
    gt = (grey_for(LT + PULL * (own - LT)) - gb) / max(1, gw - gb) * 255
    gamma = math.log(max(4, min(251, gt)) / 255) / math.log(fm / 255)
    g = g.point(lambda v: round(gb + (gw - gb) * (v / 255) ** gamma))
    duo = ImageOps.colorize(g, INK, PAPER, mid=MID)
    duo = duo.filter(ImageFilter.GaussianBlur(.6) if t.get("soft") else ImageFilter.UnsharpMask(radius=1.1, percent=55, threshold=2))
    out = Image.merge("RGBA", (*duo.split(), alpha)); stem = STEM.format(slug)
    out.save(IMGDIR / f"{stem}.webp", "WEBP", quality=88, method=6)
    for w in SMALL:  # r1: the sizes a 64-96 px circle needs at 1-3x (the srcset in rows())
        out.resize((w, w), Image.LANCZOS).save(IMGDIR / f"{stem}-{w}.webp", "WEBP", quality=86, method=6)
    return best.parent.name, fh * s / SIZE
IMGDIR.mkdir(parents=True, exist_ok=True)  # never wiped: a renamed portrait's old file stays until a day after its publish

# ---------------- markup ----------------
def bio(src_name):
    out = []
    for para in old[src_name]["bio"]:
        for s in DROP: para = para.replace(s, "")
        para = re.sub(r"\s{2,}", " ", para).strip()
        for a, b in FIX: para = para.replace(a, b)
        if para: out.append(f"<p>{H.escape(curly(para), quote=False)}</p>")
    return "".join(out)
GENERIC = {"LinkedIn", "X (Twitter)", "Faculty page"}  # labels shared by several cards: the person's name follows for screen readers
ARR_OUT = '<span class="ext" aria-hidden="true"> ↗</span>'
ARR_IN = '<svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" focusable="false"><path d="M2 8h11M9 4l4 4-4 4"/></svg>'  # r4: the site's drawn arrow
def links(src_name, extra, name):
    ls = [(("X (Twitter)" if t.startswith("X") else t), u) for t, u in old[src_name]["links"]] + extra
    ls = [("Faculty page" if t == "LinkedIn" and "linkedin.com" not in u else t, u) for t, u in ls]  # Philip's "LinkedIn" is his UW page
    out = []
    for t, u in ls:
        inside = u.startswith("blog/")
        out.append(f'<a href="{H.escape(u)}"' + ('' if inside else ' target="_blank" rel="noopener"') + f'>{H.escape(t)}'
                   + (f'<span class="sr-only"> — {H.escape(name)}</span>' if t in GENERIC else '') + (ARR_IN if inside else ARR_OUT) + '</a>')
    return "".join(out)
def srcset(slug):
    return ", ".join([f"assets/img/team/{STEM.format(slug)}-{w}.webp {w}w" for w in SMALL] + [f"assets/img/team/{STEM.format(slug)}.webp {SIZE}w"])
def rows(people, line):
    """line: the card line is drawn (the team); an advisor's row is name, kicker, bio and links (cut, 1 Nov)"""
    items, report = [], []
    for i, (slug, name, src, title, short, v1, extra) in enumerate(people):
        where, h = portrait(slug, src, v1); report.append((name, where, h))
        l = links(src, extra, name)
        card = f'<p>{whole(tie(H.escape(curly(short), quote=False)))}</p>' if line else ''
        items.append(f'''          <li id="{slug}" data-reveal style="--d:{(i % 3) * 40}ms"><div class="ph grain"><i class="ring" aria-hidden="true"></i><img src="assets/img/team/{STEM.format(slug)}.webp" srcset="{srcset(slug)}" sizes="{SIZES if line else SIZES_ADV}" alt="" width="560" height="560" loading="lazy" decoding="async"></div><div class="who"><h3>{H.escape(name)}</h3><div class="role">{H.escape(title)}</div></div><div class="what">{card}<details class="crew-more"><summary><span class="crew-more-l">Bio</span><span class="sr-only"> of {H.escape(name)}</span></summary><div class="crew-bio">{bio(src)}</div></details>{f'<div class="links">{l}</div>' if l else ''}</div></li>''')
    return "\n".join(items), report

team_html, r1 = rows(TEAM, True)
adv_html, r2 = rows(ADVISORS, False)
SECTION = f'''    <!-- 03 THE TEAM -->
    <section class="section" id="team" data-chapter="The team" data-n="03">
      <div class="container">
        <div class="ch-head ch-spread team-head">
          <h2 class="display-2 ch-title" data-reveal data-split>Systems people and market people.</h2>
          <p class="ch-line" data-reveal style="--d:80ms">Between them, they have built and led work at&nbsp;Google, Microsoft, Amazon, PayPal, Goldman&nbsp;Sachs, Bank&nbsp;of&nbsp;America and JPMorgan&nbsp;Chase.</p>
          <div class="crew-stats" data-reveal style="--d:140ms">
            <div><b>{len(TEAM)}</b><span>Team members</span></div>
            <div><b>{len(ADVISORS)}</b><span>Advisors</span></div>
            <div><b>100+</b><span>Research papers</span></div>
          </div>
        </div>
        <div class="crew-sub crew-sub--team" data-reveal><h3 class="crew-sub-h">The team</h3></div>
        <ol class="crew crew--team" role="list" aria-label="The OpenEXA team" style="--rows:{math.ceil(len(TEAM) / 2)}">
{team_html}
        </ol>
        <div class="crew-sub" data-reveal><h3 class="crew-sub-h">Advisors</h3></div>
        <ol class="crew crew--advisors" role="list" aria-label="OpenEXA advisors" style="--rows:{math.ceil(len(ADVISORS) / 2)}">
{adv_html}
        </ol>
      </div>
    </section>
'''
END = "    <!-- /THE TEAM -->"  # hc15: the section's own end marker (the team is no longer followed by §04)
page = ROOT / "company.html"
s = page.read_text(encoding="utf-8")
a, b = s.index("    <!-- 03 THE TEAM -->"), s.index(END)
page.write_text(s[:a] + SECTION + s[b:], encoding="utf-8", newline="")


def hero_still():
    """hc30r COMP-1: the hero figure at rest, as the page shows it without JavaScript: 96 agents, 12 by 8, each a 5 x 5
    bitmap (four hex digits in company-hero.js's AGENTS: bit 15 green; bits 0-14 the left three columns of five rows,
    row-major, mirrored). One unit is one cell; an agent takes 5 and the gap 2, so the sheet is 82 by 54. A mark is a
    zero-length stroke with a square cap, .72 of a cell (company.css), which keeps 1,141 marks to about 8 KB."""
    js = (ROOT / "assets" / "js" / "company-hero.js").read_text(encoding="utf-8")
    m = re.search(r"const AGENTS = '([0-9a-f]+)';", js)
    if not m or len(m.group(1)) != 96 * 4: raise SystemExit("build_team: company-hero.js has no AGENTS literal of 96 agents")
    marks = {0: [], 1: []}
    for i in range(96):
        v = int(m.group(1)[4 * i:4 * i + 4], 16)
        for y in range(5):
            for x in range(5):
                if v >> (y * 3 + (x if x < 3 else 4 - x)) & 1: marks[v >> 15 & 1].append(((i % 12) * 7 + x, (i // 12) * 7 + y))
    n = len(marks[0]) + len(marks[1])
    if n != 1 + 3 * 19 * 20: raise SystemExit(f"build_team: the 96 agents hold {n} marks; the disc of nineteen rings holds 1,141")
    def d(pts):
        out, at = [], None
        for x, y in pts:
            out.append(f"M{x + .36:g} {y + .36:g}h0" if at is None else f"m{x - at[0]} {y - at[1]}h0"); at = (x, y)
        return "".join(out)
    return ('<svg class="plate-still" viewBox="0 0 82 54" aria-hidden="true" focusable="false">'
            f'<path class="k0" d="{d(marks[0])}"/><path class="k2" d="{d(marks[1])}"/></svg>'), n, len(marks[1])

still_svg, n_marks, n_green = hero_still()
s = page.read_text(encoding="utf-8")
a, b = s.index("<!-- THE STILL -->"), s.index("<!-- /THE STILL -->")
PAD = "\n" + " " * 12
page.write_text(s[:a] + "<!-- THE STILL -->" + PAD + still_svg + PAD + s[b:], encoding="utf-8", newline="")
for name, where, h in r1 + r2: print(f"{name:24} portrait from {where:12} face {h:.0%} of the frame")
print(f"hero still: 96 agents, {n_marks} marks ({n_green} green), {len(still_svg):,} B")
print(f"team {len(TEAM)} + advisors {len(ADVISORS)}; images {len(list(IMGDIR.glob(STEM.format('*') + '.webp')))}")
