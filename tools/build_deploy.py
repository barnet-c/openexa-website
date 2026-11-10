"""The copy of site/ that Azure serves (system, award a3; stdlib only, so the deploy job needs nothing installed).

site/ stays the source, commented and readable; every check and browser suite reads it. This writes dist/site:
  1. every file of site/, as is;
  2. each stylesheet minified: comments out (outside strings and url()), whitespace collapsed (structure checked: the
     same rules and declarations as the source);
  3. each script with its comments and indentation out (a tokenizer that knows strings, template literals and regex
     literals; a script it cannot read with certainty, or that `node --check` refuses, ships as written);
  4. a second, versioned copy of each stylesheet and script at /assets/v/<sha256[:8] of its bytes>/<css|js>/<name>, and
     every reference to them in every page (href, src, data-after-paint) pointing at it; a stylesheet's url()s are
     rewritten from the site root, so they still reach the fonts and images;
  5. staticwebapp.config.json with one route more, first: /assets/v/* is "public, max-age=31536000, immutable". A
     changed file has a new address, so a returning visitor never pairs new HTML with old CSS (the reason the long cache
     waited, notes/system.md a1/a2). The unversioned copies keep the default (only old HTML still names them).
The deploy job (.github/workflows/azure-static-web-apps-*.yml) runs this and uploads dist/site; the checks job runs it
with --check (into a temporary folder; fails on any finding). To see the deployed site locally:
    python tools/build_deploy.py && python tools/serve.py 8140 --root dist/site
    python tools/build_deploy.py [--check] [--out DIR] [--no-node] [--css-bundle rest|all|none]"""
import hashlib, json, os, posixpath, re, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "site"
IMMUTABLE = "public, max-age=31536000, immutable"
problems = []

# ------------------------------------------------------------------------------------------------------------- CSS
def css_min(s):
    """Comments out, whitespace collapsed; strings and url() untouched."""
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if s.startswith("/*", i):
            j = s.find("*/", i + 2); i = n if j < 0 else j + 2
            out.append(" "); continue
        if c in "\"'":
            j = i + 1
            while j < n and s[j] != c: j += 2 if s[j] == "\\" else 1
            out.append(s[i:j + 1]); i = j + 1; continue
        if s.startswith("url(", i):
            j = i + 4
            while j < n and s[j].isspace(): j += 1
            if j < n and s[j] in "\"'":
                q = s[j]; j += 1
                while j < n and s[j] != q: j += 2 if s[j] == "\\" else 1
            j = s.find(")", j); j = n if j < 0 else j + 1
            out.append(s[i:j]); i = j; continue
        if c.isspace():
            j = i
            while j < n and s[j].isspace(): j += 1
            out.append(" "); i = j; continue
        out.append(c); i += 1
    t = "".join(out)
    # whitespace next to { } ; and after , (outside strings: they were copied whole above, and hold no such runs that
    # matter: a string's inner spaces are inside its quotes, which the next pass skips)
    res, i, n = [], 0, len(t)
    while i < n:
        c = t[i]
        if c in "\"'":
            j = i + 1
            while j < n and t[j] != c: j += 2 if t[j] == "\\" else 1
            res.append(t[i:j + 1]); i = j + 1; continue
        if t.startswith("url(", i):
            j = t.find(")", i)
            k = i + 4
            if k < n and t[k] in "\"'":
                q = t[k]; k += 1
                while k < n and t[k] != q: k += 2 if t[k] == "\\" else 1
                j = t.find(")", k)
            j = n if j < 0 else j + 1
            res.append(t[i:j]); i = j; continue
        if c == " ":
            prev = res[-1][-1:] if res else ""
            nxt = t[i + 1:i + 2]
            if prev in ("", "{", "}", ";", ",") or nxt in ("{", "}", ";", ","): i += 1; continue
        if c == "}" and res and res[-1] == ";": res.pop()
        res.append(c); i += 1
    return "".join(res).strip() + "\n"

def css_shape(s):
    """The sheet's structure, to compare source and output: rule bodies and declarations, counted outside strings."""
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    s = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', s)
    decl = len([d for d in re.split(r"[;{}]", s) if ":" in d and d.strip()])
    return s.count("{"), s.count("}"), decl

def css_urls(s, rel):
    """url(x) relative to /assets/css/<name> -> from the site root (the versioned copy lives three folders deeper)."""
    base = "/" + posixpath.dirname(rel) + "/"
    def fix(m):
        q, u = m.group(1), m.group(2)
        if re.match(r"^(?:[a-z]+:|/|#)", u): return m.group(0)
        return f"url({q}{posixpath.normpath(posixpath.join(base, u))}{q})"
    return re.sub(r"url\((['\"]?)([^'\")]+)\1\)", fix, s)

# -------------------------------------------------------------------------------------------------------------- JS
KW_BEFORE_REGEX = {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case", "do", "else",
                   "yield", "await", "extends"}

class Unsure(Exception): pass

def js_strip(src):
    """Comments out, indentation and blank lines out. Strings, template literals (with ${} nesting) and regex literals
    are copied whole and never touched. Raises Unsure where a '/' cannot be read with certainty."""
    out = []          # (text, protected)
    i, n = 0, len(src)
    prev = ""         # the last significant token: '' | 'id:<word>' | 'num' | 'str' | 'p:<c>' | 're'
    stack = []        # for each open ${: the brace depth it opened at
    depth = 0
    def emit(t, prot=False): out.append((t, prot))
    def template(j):
        """from just after a backtick (or a closing } of ${}): copy to the closing backtick or the next ${"""
        k = j
        while k < n:
            if src[k] == "\\": k += 2; continue
            if src[k] == "`": emit(src[j:k + 1], True); return k + 1, False
            if src.startswith("${", k): emit(src[j:k + 2], True); return k + 2, True
            k += 1
        raise Unsure("unterminated template literal")
    while i < n:
        c = src[i]
        if src.startswith("//", i):
            j = src.find("\n", i); i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0: raise Unsure("unterminated comment")
            emit("\n" if "\n" in src[i:j] else " "); i = j + 2
            continue
        if c in "\"'":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\n": raise Unsure("newline in a string")
                j += 2 if src[j] == "\\" else 1
            emit(src[i:j + 1], True); i = j + 1; prev = "str"; continue
        if c == "`":
            emit("`", True)
            i, opened = template(i + 1); prev = "str"
            if opened: stack.append(depth); depth += 1
            continue
        if c == "{": depth += 1; emit(c); prev = "p:{"; i += 1; continue
        if c == "}":
            depth -= 1
            if stack and depth == stack[-1]:
                stack.pop()
                emit("}", True)
                i, opened = template(i + 1); prev = "str"
                if opened: stack.append(depth); depth += 1
                continue
            emit(c); prev = "p:}"; i += 1; continue
        if c == "/":
            word = prev[3:] if prev.startswith("id:") else ""
            regex = prev in ("", "re") or (prev.startswith("p:") and prev not in ("p:)", "p:]", "p:}")) or word in KW_BEFORE_REGEX
            # after ) ] } or a name a '/' divides. A regex there (`if (x) /re/.test(y)`) is read as division, harmless unless
            # it holds // or /*: then the stripped copy no longer parses (node --check) and the file ships as written
            if regex:
                j, cls = i + 1, False
                while j < n:
                    ch = src[j]
                    if ch == "\n": raise Unsure("regex literal runs into a newline")
                    if ch == "\\": j += 2; continue
                    if ch == "[": cls = True
                    elif ch == "]": cls = False
                    elif ch == "/" and not cls: break
                    j += 1
                j += 1
                while j < n and (src[j].isalpha()): j += 1
                emit(src[i:j], True); i = j; prev = "re"; continue
            emit(c); prev = "p:/"; i += 1; continue
        if c.isalpha() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"): j += 1
            emit(src[i:j]); prev = "id:" + src[i:j]; i = j; continue
        if c.isdigit() or (c == "." and src[i + 1:i + 2].isdigit()):
            j = i
            while j < n and (src[j].isalnum() or src[j] in "._"): j += 1
            emit(src[i:j]); prev = "num"; i = j; continue
        if c.isspace(): emit(c); i += 1; continue
        emit(c); prev = "p:" + c; i += 1
    if stack: raise Unsure("unclosed ${")
    # indentation and blank lines: only where a line starts outside a protected run
    text = []
    at_line_start = True
    for t, prot in out:
        if prot:
            text.append(t); at_line_start = False
            continue
        for ch in t:
            if ch == "\n":
                # trailing spaces of the line before
                while text and text[-1] in (" ", "\t"): text.pop()
                if text and text[-1] != "\n": text.append("\n")
                elif not text: pass
                at_line_start = True
            elif ch in " \t" and at_line_start: continue
            else: text.append(ch); at_line_start = False
    return "".join(text).strip() + "\n"

def node_ok(path):
    try: return subprocess.run(["node", "--check", str(path)], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError): return None

# ---------------------------------------------------------------------------------------------------------- bundles
LINK = re.compile(r'<link rel="stylesheet" href="([^"]+)">')

def bundle_css(out, versioned, mode):
    """(award a4) A page's run of stylesheet links, joined into one versioned sheet in the same order (the cascade is
    the same: one sheet after another is one sheet). mode "rest" keeps site.css on its own, so the sheet every page
    shares stays cached from page to page, and joins what follows it (Home 7 -> 2, Platform 4 -> 2, Proof and Trust
    3 -> 2; a page with one sheet after site.css is unchanged); "all" joins the run whole (one sheet a page, site.css in
    each). The bodies are the versioned copies (url()s already from the site root)."""
    vbody = {rel: (out / v).read_text(encoding="utf-8") for rel, v in versioned.items() if rel.startswith("assets/css/")}
    back = {v: rel for rel, v in versioned.items()}
    made = {}
    for page in sorted(out.rglob("*.html")):
        prel = page.relative_to(out).as_posix()
        pdir = posixpath.dirname(prel)
        s = page.read_text(encoding="utf-8")
        def target(u):
            t = u.lstrip("/") if u.startswith("/") else posixpath.normpath(posixpath.join(pdir, u))
            return back.get(t)
        def join(m):
            run = m.group(0)
            links = LINK.findall(run)
            rels = [target(u) for u in links]
            if None in rels: return run
            head, rels = ([], rels) if mode == "all" else (rels[:1], rels[1:]) if rels[0] == "assets/css/site.css" else ([], rels)
            if len(rels) < 2: return run
            body = "".join(vbody[r] if vbody[r].endswith("\n") else vbody[r] + "\n" for r in rels)
            h = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
            name = "-".join(posixpath.splitext(posixpath.basename(r))[0] for r in rels)
            vrel = f"assets/v/{h}/css/set-{name}.css"
            if vrel not in made:
                (out / vrel).parent.mkdir(parents=True, exist_ok=True)
                (out / vrel).write_text(body, encoding="utf-8", newline="\n")
                made[vrel] = rels
            href = lambda v: "/" + v if links[0].startswith("/") else posixpath.relpath(v, pdir or ".")
            sep = re.search(r">(\s*)<link", run)
            gap = sep.group(1) if sep else "\n"
            return gap.join([f'<link rel="stylesheet" href="{href(versioned[r])}">' for r in head] + [f'<link rel="stylesheet" href="{href(vrel)}">'])
        s2 = re.sub(r'(?:<link rel="stylesheet" href="[^"]+">\s*)*<link rel="stylesheet" href="[^"]+">', join, s)
        if s2 != s: page.write_text(s2, encoding="utf-8", newline="\n")
    return len(made)

# ----------------------------------------------------------------------------------------------------------- build
def build(out, use_node=True, css_bundle="rest"):
    if out == REPO or out == SRC or SRC in out.parents or out in SRC.parents:
        sys.exit(f"build_deploy: refusing to write into {out} (it holds the source)")
    if out.exists(): shutil.rmtree(out)
    shutil.copytree(SRC, out)
    versioned = {}   # 'assets/css/site.css' -> 'assets/v/<h>/css/site.css'
    report = {"css": 0, "css_saved": 0, "js": 0, "js_saved": 0, "js_kept": []}
    for kind in ("css", "js"):
        for f in sorted((out / "assets" / kind).glob(f"*.{kind}")):
            rel = f"assets/{kind}/{f.name}"
            src = f.read_text(encoding="utf-8")
            if kind == "css":
                body = css_min(src)
                if css_shape(body) != css_shape(src):
                    problems.append(f"{rel}: the minified sheet's structure differs {css_shape(src)} -> {css_shape(body)}; shipped as written")
                    body = src
                report["css"] += 1; report["css_saved"] += len(src.encode()) - len(body.encode())
            else:
                try: body = js_strip(src)
                except Unsure as e: report["js_kept"].append(f"{f.name} ({e})"); body = src
                if body is not src:
                    f.write_text(body, encoding="utf-8", newline="\n")
                    if use_node and node_ok(f) is False:
                        report["js_kept"].append(f"{f.name} (node --check refused the stripped copy)"); body = src
                report["js"] += 1; report["js_saved"] += len(src.encode()) - len(body.encode())
            f.write_text(body, encoding="utf-8", newline="\n")
            h = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
            vrel = f"assets/v/{h}/{kind}/{f.name}"
            vbody = css_urls(body, rel) if kind == "css" else body
            (out / vrel).parent.mkdir(parents=True, exist_ok=True)
            (out / vrel).write_text(vbody, encoding="utf-8", newline="\n")
            versioned[rel] = vrel
    # every page: href / src / data-after-paint
    pages = 0
    for page in sorted(out.rglob("*.html")):
        prel = page.relative_to(out).as_posix()
        pdir = posixpath.dirname(prel)
        s = page.read_text(encoding="utf-8")
        def resolve(u):
            if re.match(r"^[a-z]+:", u): return None
            path = u.split("#")[0].split("?")[0]
            target = posixpath.normpath(path.lstrip("/") if path.startswith("/") else posixpath.join(pdir, path))
            return target if target in versioned else None
        def swap(u):
            t = resolve(u)
            if not t: return u
            v = versioned[t]
            if u.startswith("/"): return "/" + v
            return posixpath.relpath(v, pdir or ".")
        s2 = re.sub(r'\b(href|src)="([^"]+)"', lambda m: f'{m.group(1)}="{swap(m.group(2))}"', s)
        s2 = re.sub(r'\bdata-after-paint="([^"]*)"', lambda m: 'data-after-paint="' + " ".join(swap(u) for u in m.group(1).split()) + '"', s2)
        left = [u for u in re.findall(r'(?:href|src)="([^"]+)"', s2) if resolve(u)]
        left += [u for m in re.findall(r'data-after-paint="([^"]*)"', s2) for u in m.split() if resolve(u)]
        if left: problems.append(f"{prel}: unversioned asset references left: {left}")
        if s2 != s: page.write_text(s2, encoding="utf-8", newline="\n"); pages += 1
    report["bundles"] = bundle_css(out, versioned, css_bundle) if css_bundle != "none" else 0
    # every versioned reference resolves to a file
    for page in out.rglob("*.html"):
        pdir = posixpath.dirname(page.relative_to(out).as_posix())
        for u in re.findall(r'(?:href|src)="([^"]*assets/v/[^"]+)"', page.read_text(encoding="utf-8")):
            t = u.lstrip("/") if u.startswith("/") else posixpath.normpath(posixpath.join(pdir, u))
            if not (out / t).is_file(): problems.append(f"{page.name}: {u} does not exist")
    # the cache route, first
    cfg_p = out / "staticwebapp.config.json"
    cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
    cfg["routes"] = [{"route": "/assets/v/*", "headers": {"Cache-Control": IMMUTABLE}}] + [r for r in cfg.get("routes", []) if r.get("route") != "/assets/v/*"]
    cfg_p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    report["pages"] = pages; report["files"] = len(versioned)
    return report

if __name__ == "__main__":
    args = sys.argv[1:]
    check = "--check" in args
    use_node = "--no-node" not in args
    out = Path(args[args.index("--out") + 1]) if "--out" in args else (Path(tempfile.mkdtemp()) / "site" if check else REPO / "dist" / "site")
    css_bundle = args[args.index("--css-bundle") + 1] if "--css-bundle" in args else "rest"
    if css_bundle not in ("none", "rest", "all"): sys.exit("build_deploy: --css-bundle none|rest|all")
    rep = build(out.resolve(), use_node, css_bundle)
    print(f"build_deploy: {rep['pages']} pages, {rep['files']} versioned assets in {out}; CSS {rep['css']} sheets "
          f"-{rep['css_saved']:,} B; JS {rep['js']} scripts -{rep['js_saved']:,} B; {rep['bundles']} stylesheet sets ({css_bundle})" +
          (f"; shipped as written: {', '.join(rep['js_kept'])}" if rep["js_kept"] else ""))
    for p in problems: print("PROBLEM", p)
    if check: shutil.rmtree(out.parent if out.name == "site" and out.parent.name.startswith("tmp") else out, ignore_errors=True)
    sys.exit(1 if problems else 0)
