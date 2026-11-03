"""Repository-relative locations shared by every tool (the scripts were written against absolute paths)."""
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "site"                     # the website, exactly as deployed
DATA = REPO / "data"                     # inputs: scraped old blog + team, research markdown, v1 portraits; generated summaries
SHOTS = REPO / ".shots"                  # screenshots written by the verify scripts (git-ignored)
DIST = REPO / "dist"                     # deploy ZIPs (git-ignored)
ARCHIVE = REPO.parent / "openexa-versions"   # optional sibling checkout of barnet-c/openexa-website-versions
SHOTS.mkdir(exist_ok=True)
DIST.mkdir(exist_ok=True)

def og_name(path):
    """File name of the social card tools/build_og.py renders for a page: 'research/01-x.html' -> 'research-01-x.jpg'."""
    path = path or "index.html"
    if path.endswith("/"): path += "index.html"
    return path[:-5].replace("/", "-") + ".jpg"

def og_image(url):
    """Absolute og:image URL for the page at `url` (https://www.openexa.com/...)."""
    return "https://www.openexa.com/assets/img/og/" + og_name(url.replace("https://www.openexa.com/", ""))
