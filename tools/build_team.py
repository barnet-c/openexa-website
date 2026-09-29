"""Rebuild the Company page's team section (03) from the old openexa.com About page (/status/), in the site's own design.

Source: oldteam/team.json + portraits, scraped from https://www.openexa.com/status/ (2026-09-29).
Changes from the source, deliberately:
  - Barnet Sherman removed (now a customer).
  - Ajit: no patent count (his request); his short line is the current AI-company one.
  - Titles for the five people already on the site keep their current C-level titles; everyone else uses the About page's.
  - Sentences describing OpenEXA's former crypto business as someone's current work are dropped (Victor, Abhishek,
    Shalabh); career facts are kept as written (Tim's research areas, Mike's systems work, Sreeram's lab).
  - Julius's short line drops "Crypto" from "AML & Crypto Risk"; John's surname follows his bio and LinkedIn (Schuster).
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import html as H, io, json, re, shutil
from pathlib import Path
from PIL import Image, ImageFilter

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
# (slug, display name, source name, title, short line, v1 photo or None, extra links)
TEAM = [
    ("ajit-dubey", "Ajit K Dubey", "Ajit K Dubey", "Founder · CEO", "Founder and CEO of OpenEXA. Big Tech and capital-markets veteran, building the foundational infrastructure for agentic lifecycles.", "ajit-dubey", []),
    ("tim-leung", "Dr. Tim Leung", "Tim Leung, Ph.D.", "Chief Scientist", "Boeing Endowed Chair Professor of Applied Mathematics and Director of Computational Finance & Risk Management at the University of Washington.", "tim-leung", [("More on financial markets research ↗", SCHOLAR)]),
    ("mike-lockhart", "Mike Lockhart", "Mike Lockhart", "Chief Technology", "Architect of high-stakes systems, including those that touch 90% of Microsoft's revenue.", "mike-lockhart", []),
    ("victor-gamolsky", "Victor Gamolsky", "Victor Gamolsky", "Chief Product", "A decade of building and scaling ventures with lean, evidence-driven product methods.", "victor-gamolsky", []),
    ("shalabh-choudhri", "Shalabh Choudhri", "Shalabh Choudhri", "Chief AI Agents", "Leads agent research and the post-trained models behind OpenEXA's domain-specific execution agents.", "shalabh-choudhri", []),
    ("john-schuster", "John Schuster", "John Shuster", "Strategy & Markets", "A startup founder and executive, with an MBA in Finance from The Wharton School.", None, []),
    ("subuddh-parekh", "Subuddh Parekh", "Subuddh Parekh", "SME · AI & ML", "Engineering, product and machine-learning expert, with a BS and MS in Computer Science from Stanford.", None, []),
    ("abhishek-sinha", "Abhishek Sinha", "Abhishek Sinha", "Program Manager · Technology", "A technology expert with over a decade of experience delivering v1 initiatives on the ground.", None, []),
    ("julius-ekeroma", "Dr. Julius E. Ekeroma", "Dr. Julius E. Ekeroma, Ph.D.", "Compliance & Risk", "Chief Compliance · AML & Risk. 25+ years in auditing, operations and financial forensics.", None, []),
    ("dipit-nanawati", "Dipit Nanawati", "Dipit Nanawati", "SME · Financial Markets", "A trusted advisor to some of Wall Street's largest firms on operational efficiency, compliance and profitability.", None, []),
]
ADVISORS = [
    ("kumar-mehta", "Kumar Mehta", "Kumar Mehta", "Advisor", "Co-founder and CDO, and former CEO, of Versa Networks.", None, []),
    ("sreeram-kannan", "Sreeram Kannan", "Sreeram Kannan", "Advisor", "Founder and CEO of Eigen Layer and director of the University of Washington's Blockchain Lab.", None, []),
    ("philip-bond", "Dr. Philip Bond", "Philip Bond, Ph.D.", "Advisor", "Distinguished Professor of Capital Markets, Business, Finance and Economics.", None, [("His research on the blog →", "research/blog/index.html#economics")]),
]

# ---------------- portraits ----------------
SIZE, HEADROOM = 560, 0.06
def subject(path):
    im = Image.open(path).convert("RGBA"); box = im.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
    return im, box
def portrait(slug, src_name, v1_name):
    cands = [SRC / Path(old[src_name]["img"]).name]
    if v1_name: cands.append(V1 / f"{v1_name}.png")
    best = max(cands, key=lambda c: subject(c)[1][3] - subject(c)[1][1])  # the tallest subject = most real pixels
    im, box = subject(best); sub = im.crop(box); w, h = sub.size
    side = max(w, int(round(h * (1 + HEADROOM))))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0)); canvas.paste(sub, ((side - w) // 2, side - h))
    out = canvas.resize((SIZE, SIZE), Image.LANCZOS)
    rgb = out.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.1, percent=55, threshold=2))
    out = Image.merge("RGBA", (*rgb.split(), out.getchannel("A")))
    out.save(IMGDIR / f"{slug}.webp", "WEBP", quality=90, method=6)
    return best.parent.name, h
if IMGDIR.exists(): shutil.rmtree(IMGDIR)
IMGDIR.mkdir(parents=True)

# ---------------- markup ----------------
def bio(src_name):
    out = []
    for para in old[src_name]["bio"]:
        for s in DROP: para = para.replace(s, "")
        para = re.sub(r"\s{2,}", " ", para).strip()
        if para: out.append(f"<p>{H.escape(para, quote=False)}</p>")
    return "".join(out)
def links(src_name, extra):
    ls = [(("X" if t.startswith("X") else t), u) for t, u in old[src_name]["links"]] + extra
    return "".join(f'<a href="{H.escape(u)}"' + ('' if u.startswith("research/") else ' target="_blank" rel="noopener"') + f'>{H.escape(t)}</a>' for t, u in ls)
def cards(people, prefix, cols):
    items, report = [], []
    for i, (slug, name, src, title, short, v1, extra) in enumerate(people):
        where, h = portrait(slug, src, v1); report.append((name, where, h))
        l = links(src, extra)
        items.append(f'''          <li data-reveal style="--d:{60 + (i % cols) * 60}ms"><div class="n"><span>{prefix}-{i + 1:02d}</span></div><div class="ph grain"><i class="ring" aria-hidden="true"></i><img src="assets/img/team/{slug}.webp" alt="{H.escape(name)}" width="560" height="560" loading="lazy" decoding="async"></div><div class="role">{H.escape(title)}</div><h3>{H.escape(name)}</h3><p>{H.escape(short, quote=False)}</p>{f'<div class="links">{l}</div>' if l else ''}<details class="crew-more"><summary>Read full description</summary><div class="crew-bio">{bio(src)}</div></details></li>''')
    return "\n".join(items), report

WORDS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve"]
team_html, r1 = cards(TEAM, "T", 5)
adv_html, r2 = cards(ADVISORS, "A", 3)
SECTION = f'''    <!-- 03 THE TEAM -->
    <section class="section" id="team">
      <div class="container">
        <div class="sec-head" data-reveal><span class="idx">03</span><span class="lab">The team</span><span class="aside">Big Tech · Wall Street · the academy</span></div>
        <div class="grid mb-3">
          <div class="col-6"><h2 class="display-2" data-reveal data-split>Systems people and market people, under one roof.</h2></div>
          <div class="col-5 offset-7">
            <p class="body-lg" data-reveal style="--d:80ms">{WORDS[len(TEAM)]} people and {WORDS[len(ADVISORS)].lower()} advisors from technology and finance, with deep experience in AI, capital markets and financial innovation. Between them, they have built and led work at Google, Microsoft, Amazon, PayPal, Goldman Sachs, Bank of America and JPMorgan Chase, and they now build the agents that run Lifecycle 01.</p>
            <div class="crew-stats" data-reveal style="--d:140ms">
              <div><b data-count="{len(TEAM)}">{len(TEAM)}</b><span>Team members</span></div>
              <div><b data-count="{len(ADVISORS)}">{len(ADVISORS)}</b><span>Advisors</span></div>
              <div><b data-count="100" data-suffix="+">100+</b><span>Research papers</span></div>
            </div>
          </div>
        </div>
        <ol class="crew crew--team" aria-label="The OpenEXA team">
{team_html}
        </ol>
        <div class="crew-sub" data-reveal><h3 class="crew-sub-h">Advisors</h3><p>Operators and scholars who advise OpenEXA on networks, distributed systems and the economics of financial markets.</p></div>
        <ol class="crew crew--advisors" aria-label="OpenEXA advisors">
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
print(f"team {len(TEAM)} + advisors {len(ADVISORS)}; images {len(list(IMGDIR.iterdir()))}")
