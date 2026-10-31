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
    (<slug>-v2x.webp); the old files are left in place for pages cached before the change.
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
    ("An expert in compliance and financial risk with", "Julius is an expert in compliance and financial risk with"),
    ("Ph.D. in Business Analytics, expert in", "He holds a Ph.D. in Business Analytics and is an expert in"),
    ("and trade surveillance. Integrating data sets, performing analytical calculations, building and configuring models, performing model validation and tuning.",
     "and trade surveillance. His work includes integrating data sets, performing analytical calculations, building and configuring models, and performing model validation and tuning."),
]
def curly(s):  # typography: apostrophes as U+2019 (VOICE §7); no quotation marks occur in these texts
    return s.replace("'", "’")
# (slug, display name, source name, title, short line, v1 photo or None, extra links)
TEAM = [
    ("ajit-dubey", "Ajit K Dubey", "Ajit K Dubey", "Founder · CEO", "Founder and CEO of OpenEXA. Big Tech and capital-markets veteran, building the foundational infrastructure for agentic lifecycles.", "ajit-dubey", []),
    ("tim-leung", "Dr. Tim Leung", "Tim Leung, Ph.D.", "Chief Scientist", "Boeing Endowed Chair Professor of Applied Mathematics and Director of Computational Finance & Risk Management at the University of Washington.", "tim-leung", [("More on financial markets research", SCHOLAR)]),
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
    ("sreeram-kannan", "Sreeram Kannan", "Sreeram Kannan", "Advisor · Blockchain Systems", "Founder and CEO of Eigen Layer and director of the University of Washington's Blockchain Lab.", None, []),
    ("philip-bond", "Dr. Philip Bond", "Philip Bond, Ph.D.", "Advisor · Capital Markets", "Distinguished Professor of Capital Markets, Business, Finance and Economics.", None, [("His research on the blog", "blog/index.html#economics")]),
    ("john-schuster", "John Schuster", "John Shuster", "Advisor · Strategy & Markets", "A startup founder and executive, with an MBA in Finance from The Wharton School.", None, []),
    ("victor-gamolsky", "Victor Gamolsky", "Victor Gamolsky", "Advisor · Strategy & Technology", "A decade of building and scaling ventures with lean, evidence-driven product methods.", "victor-gamolsky", []),
    ("abhishek-sinha", "Abhishek Sinha", "Abhishek Sinha", "Advisor · Technology Programs", "A technology expert with over a decade of experience delivering v1 initiatives on the ground.", None, []),
    ("julius-ekeroma", "Dr. Julius E. Ekeroma", "Dr. Julius E. Ekeroma, Ph.D.", "Advisor · Compliance & Risk", "Expert in compliance and financial risk, with 25+ years in auditing, operations and financial forensics.", None, []),
    ("dipit-nanawati", "Dipit Nanawati", "Dipit Nanawati", "Advisor · Financial Markets", "A trusted advisor to some of Wall Street's largest firms on operational efficiency, compliance and profitability.", None, []),
    ("subuddh-parekh", "Subuddh Parekh", "Subuddh Parekh", "Advisor · AI & ML", "Engineering, product and machine-learning expert, with a BS and MS in Computer Science from Stanford.", None, []),
]

# ---------------- portraits: one treatment for all thirteen ----------------
# The sources are cut-outs from different cameras, crops and exposures. Each is set the same way: the head (measured
# on the cut-out's alpha, the median row width of the band 6-20% down the subject, so neither a hat brim nor the
# shoulders) is scaled to HEAD_W of the frame and its top placed at HEAD_TOP; the body always reaches the bottom edge;
# a side where the photo itself was cut through the head stays outside the frame. Tones are stretched on the subject
# (2nd-98.5th percentile), the midtone brought to one level, then printed ink (#0E1512) on paper (#F5F2EC).
# TUNE corrects what a measurement cannot know: Mike's only photo is a small holiday snapshot (zoomed past the child
# beside him; half the stretch, softened, since its noise is not detail); Subuddh's hat is not his head; John's photo
# is cut behind his head.
SIZE, HEAD_W, HEAD_TOP = 560, 0.34, 0.14
INK, PAPER, MID = (14, 21, 18), (245, 242, 236), (112, 112, 104)
TUNE = {"Mike Lockhart": dict(k=1.22, soft=True), "Subuddh Parekh": dict(k=0.66, top=0.035), "John Shuster": dict(k=1.15)}
def subject(path):
    im = Image.open(path).convert("RGBA"); box = im.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
    return im, box
def head_span(sub):
    a = sub.getchannel("A").point(lambda v: 255 if v > 96 else 0); w, h = a.size; px = a.load(); rows = []
    for y in range(int(h * 0.06), int(h * 0.20) + 1):
        xs = [x for x in range(0, w, 2) if px[x, y]]
        if xs: rows.append((xs[0], xs[-1]))
    rows.sort(key=lambda r: r[1] - r[0])
    return rows[len(rows) // 2]
def cut_sides(im, box):
    a = im.getchannel("A"); W, _ = im.size; x0, y0, x1, y1 = box; px = a.load(); upper = range(y0, y0 + (y1 - y0) // 2)
    return (x0 == 0 and sum(1 for y in upper if px[0, y] > 128) > 8, x1 == W and sum(1 for y in upper if px[W - 1, y] > 128) > 8)
def portrait(slug, src_name, v1_name):
    cands = [SRC / Path(old[src_name]["img"]).name]
    if v1_name: cands.append(V1 / f"{v1_name}.png")
    best = max(cands, key=lambda c: subject(c)[1][3] - subject(c)[1][1])  # the tallest subject = most real pixels
    im, box = subject(best); sub = im.crop(box); cut_l, cut_r = cut_sides(im, box); t = TUNE.get(src_name, {})
    w, h = sub.size; l, r = head_span(sub); top = t.get("top", HEAD_TOP)
    s = max(SIZE * HEAD_W * t.get("k", 1) / max(1, r - l), SIZE * (1 - top) / h)
    sub = sub.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    x = SIZE / 2 - (l + r) / 2 * s
    if cut_l: x = min(x, 0)
    if cut_r: x = max(x, SIZE - sub.size[0])
    x, y = round(x), round(SIZE * top)
    sub = sub.crop((max(0, -x), max(0, -y), sub.size[0], sub.size[1]))
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0)); canvas.alpha_composite(sub, (max(0, x), max(0, y)))
    alpha = canvas.getchannel("A"); g = canvas.convert("RGB").convert("L")
    on = lambda img: sorted(v for v, al in zip(img.tobytes(), alpha.tobytes()) if al > 160)
    vals = on(g); lo, hi = vals[int(len(vals) * .02)], vals[int(len(vals) * .985)]
    q = .55 if t.get("soft") else 1.0
    g = g.point(lambda v: max(0, min(255, round(v + q * ((v - lo) * 255 / max(1, hi - lo) - v)))))
    med = on(g)[len(vals) // 2]
    gamma = math.log(0.52) / math.log(max(.05, min(.95, med / 255)))
    if t.get("soft"): gamma = 1 + (gamma - 1) * .5
    g = g.point(lambda v: round(255 * (v / 255) ** gamma))
    duo = ImageOps.colorize(g, INK, PAPER, mid=MID)
    duo = duo.filter(ImageFilter.GaussianBlur(.6) if t.get("soft") else ImageFilter.UnsharpMask(radius=1.1, percent=55, threshold=2))
    out = Image.merge("RGBA", (*duo.split(), alpha))
    out.save(IMGDIR / f"{slug}-v2x.webp", "WEBP", quality=88, method=6)
    return best.parent.name, h
IMGDIR.mkdir(parents=True, exist_ok=True)  # v2x: the v2 files stay for pages cached before the change

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
ARR_IN = '<span class="int" aria-hidden="true"> →</span>'
def links(src_name, extra, name):
    ls = [(("X (Twitter)" if t.startswith("X") else t), u) for t, u in old[src_name]["links"]] + extra
    ls = [("Faculty page" if t == "LinkedIn" and "linkedin.com" not in u else t, u) for t, u in ls]  # Philip's "LinkedIn" is his UW page
    out = []
    for t, u in ls:
        inside = u.startswith("blog/")
        out.append(f'<a href="{H.escape(u)}"' + ('' if inside else ' target="_blank" rel="noopener"') + f'>{H.escape(t)}'
                   + (f'<span class="sr-only"> — {H.escape(name)}</span>' if t in GENERIC else '') + (ARR_IN if inside else ARR_OUT) + '</a>')
    return "".join(out)
def rows(people, prefix):
    items, report = [], []
    for i, (slug, name, src, title, short, v1, extra) in enumerate(people):
        where, h = portrait(slug, src, v1); report.append((name, where, h))
        l = links(src, extra, name)
        items.append(f'''          <li id="{slug}" data-reveal style="--d:{(i % 3) * 40}ms"><div class="n"><span>{prefix}-{i + 1:02d}</span></div><div class="ph grain"><i class="ring" aria-hidden="true"></i><img src="assets/img/team/{slug}-v2x.webp" alt="" width="560" height="560" loading="lazy" decoding="async"></div><div class="who"><h3>{H.escape(name)}</h3><div class="role">{H.escape(title)}</div></div><div class="what"><p>{H.escape(curly(short), quote=False)}</p><details class="crew-more"><summary><span class="when-shut">Read the full bio</span><span class="when-open">Close the bio</span><span class="sr-only"> for {H.escape(name)}</span></summary><div class="crew-bio">{bio(src)}</div></details>{f'<div class="links">{l}</div>' if l else ''}</div></li>''')
    return "\n".join(items), report

WORDS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve"]
team_html, r1 = rows(TEAM, "T")
adv_html, r2 = rows(ADVISORS, "A")
SECTION = f'''    <!-- 03 THE TEAM -->
    <section class="section" id="team">
      <div class="container">
        <div class="sec-head" data-reveal><span class="idx">03</span><span class="lab">The team</span><span class="aside">Big Tech · Wall Street · the academy</span></div>
        <div class="grid t-2 team-head">
          <div class="col-6"><h2 class="display-2" data-reveal data-split>Systems people and market people, under one roof.</h2></div>
          <div class="col-5 offset-7">
            <p class="body-lg" data-reveal style="--d:80ms">{WORDS[len(TEAM)]} people build the agents that run Lifecycle 01, guided by {WORDS[len(ADVISORS)].lower()} advisors from technology, finance and the academy. Between them, they have built and led work at Google, Microsoft, Amazon, PayPal, Goldman Sachs, Bank of America and JPMorgan Chase, with deep experience in AI, capital markets and financial innovation.</p>
            <div class="crew-stats" data-reveal style="--d:140ms">
              <div><b>{len(TEAM)}</b><span>Team members</span></div>
              <div><b>{len(ADVISORS)}</b><span>Advisors</span></div>
              <div><b>100+</b><span>Research papers</span></div>
            </div>
          </div>
        </div>
        <div class="crew-sub crew-sub--team" data-reveal><h3 class="crew-sub-h">The team</h3></div>
        <ol class="crew crew--team" role="list" aria-label="The OpenEXA team">
{team_html}
        </ol>
        <div class="crew-sub" data-reveal><h3 class="crew-sub-h">Advisors</h3><p>Operators, scholars and specialists who advise OpenEXA on strategy, AI and machine learning, compliance and risk, networks, distributed systems and the economics of financial markets.</p></div>
        <ol class="crew crew--advisors" role="list" aria-label="OpenEXA advisors">
{adv_html}
        </ol>
      </div>
    </section>

'''
page = ROOT / "company.html"
s = page.read_text(encoding="utf-8")
a, b = s.index("    <!-- 03 THE TEAM -->"), s.index("    <!-- 04 FOUR CONSTANTS -->")
page.write_text(s[:a] + SECTION + s[b:], encoding="utf-8", newline="")
for name, where, h in r1 + r2: print(f"{name:24} portrait from {where:12} subject {h}px")
print(f"team {len(TEAM)} + advisors {len(ADVISORS)}; images {len(list(IMGDIR.glob('*-v2x.webp')))}")
