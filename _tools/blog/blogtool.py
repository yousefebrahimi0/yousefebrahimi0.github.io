#!/usr/bin/env python3
"""yousef.uk blog tool: the one way to turn a .docx + image folder into a post.

Subcommands
  image   optimize one image into /blog/images/<slug>/<name>-{480,960,1600}.webp (+ OG jpg for the feature)
  post    .docx + images + placement -> _posts/YYYY-MM-DD-<slug>.md + optimized images
  check   validate every post (front matter, category, images, alt text, stray unicode)

Run from anywhere; paths resolve against the repo root (two levels up from this file).
Needs: Pillow (WebP), mammoth (docx). Never publishes: _tools/ is ignored by Jekyll.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POSTS = ROOT / "_posts"
CATS = ROOT / "_blog_categories"
IMAGES = ROOT / "blog" / "images"
WIDTHS = (480, 960, 1600)
WEBP_QUALITY = 78
OG_SIZE = (1200, 630)
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FIG_RE = re.compile(r"\{%\s*include\s+blog/figure\.html\s+(.*?)%\}")
# Characters that must never land in a post: zero-width, bidi controls, BOM, soft hyphen.
INVISIBLE_RE = re.compile("[\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")


# ---------------------------------------------------------------- images
@dataclass
class ImageMeta:
    name: str
    w: int
    h: int


def optimize_image(src: Path, slug: str, name: str, og: bool = False) -> ImageMeta:
    """EXIF-orient, strip metadata, sRGB, write WebP at 480/960/1600 (never upscaled)."""
    from PIL import Image, ImageOps

    out_dir = IMAGES / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        if im.mode == "RGBA":  # flatten onto the dark page colour
            bg = Image.new("RGB", im.size, (17, 17, 17))
            bg.paste(im, mask=im.split()[3])
            im = bg
        largest = None
        for w in WIDTHS:
            tw = min(w, im.width)
            th = round(im.height * tw / im.width)
            resized = im if tw == im.width else im.resize((tw, th), Image.LANCZOS)
            resized.save(out_dir / f"{name}-{w}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
            largest = (tw, th)
        if og:
            ImageOps.fit(im, OG_SIZE, Image.LANCZOS, centering=(0.5, 0.5)).save(
                out_dir / f"{name}-og.jpg", "JPEG", quality=84, optimize=True, progressive=True
            )
    return ImageMeta(name, *largest)


# ---------------------------------------------------------------- docx -> markdown
class _MD(HTMLParser):
    """Small HTML->Markdown converter for mammoth output (headings, paragraphs, emphasis, links, lists, quotes)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.buf: list[str] = []
        self.lists: list[str] = []
        self.href: list[str] = []
        self.block = None

    def _flush(self, prefix: str = "") -> None:
        text = re.sub(r"[ \t]+", " ", "".join(self.buf)).strip()
        self.buf = []
        if text:
            self.out.append(prefix + text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "p", "blockquote"):
            self.block = tag
        elif tag in ("ul", "ol"):
            self.lists.append(tag)
        elif tag == "li":
            self.buf = []
        elif tag in ("strong", "b"):
            self.buf.append("**")
        elif tag in ("em", "i"):
            self.buf.append("*")
        elif tag == "a":
            self.href.append(a.get("href", ""))
            self.buf.append("[")
        elif tag == "br":
            self.buf.append(" ")

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4"):
            self._flush("#" * int(tag[1]) + " ")
        elif tag == "p":
            if self.lists:
                return
            self._flush("> " if self.block == "blockquote" else "")
        elif tag == "li":
            n = "1. " if self.lists and self.lists[-1] == "ol" else "- "
            self._flush(n)
        elif tag in ("ul", "ol"):
            self.lists.pop()
        elif tag in ("strong", "b"):
            self.buf.append("**")
        elif tag in ("em", "i"):
            self.buf.append("*")
        elif tag == "a":
            self.buf.append(f"]({self.href.pop()})")

    def handle_data(self, data):
        self.buf.append(data)


def docx_to_markdown(path: Path) -> str:
    import mammoth

    with path.open("rb") as f:
        result = mammoth.convert_to_html(f, convert_image=mammoth.images.img_element(lambda i: {"src": ""}))
    p = _MD()
    p.feed(result.value)
    md = "\n\n".join(p.out)
    md = re.sub(r"(?m)^((?:- |1\. ).*)\n\n(?=(?:- |1\. ))", r"\1\n", md)  # keep lists tight
    md = re.sub(r"(?m)^((?:- |1\. ).*)\n\n(?=(?:- |1\. ))", r"\1\n", md)
    md = md.replace("****", "").replace("**  **", " ")
    return clean_text(md)


def clean_text(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = INVISIBLE_RE.sub("", s).replace("\u00a0", " ")
    return re.sub(r"\n{3,}", "\n\n", s).strip() + "\n"


# ---------------------------------------------------------------- placement
@dataclass
class Placement:
    n: int
    mode: str  # "marker" | "after-text" | "after-heading"
    needle: str = ""


def parse_place(spec: str) -> Placement:
    """'3:after-text=When I joined' or '2:after-heading=The audit'."""
    n, rule = spec.split(":", 1)
    mode, needle = rule.split("=", 1)
    if mode not in ("after-text", "after-heading"):
        raise SystemExit(f"bad --place mode: {mode}")
    return Placement(int(n), mode, needle.strip())


def figure_tag(meta: ImageMeta, alt: str, caption: str = "", wide: bool = False) -> str:
    parts = [f'name="{meta.name}"', f'alt="{alt.replace(chr(34), "&quot;")}"']
    if caption:
        parts.append(f'caption="{caption.replace(chr(34), "&quot;")}"')
    parts += [f"w={meta.w}", f"h={meta.h}"]
    if wide:
        parts.append("wide=true")
    return "{% include blog/figure.html " + " ".join(parts) + " %}"


def place_figures(md: str, figures: dict[int, str], rules: list[Placement]) -> tuple[str, list[int]]:
    blocks = md.strip().split("\n\n")
    placed: list[int] = []
    # 1) [IMG n] markers typed in the docx
    for i, b in enumerate(blocks):
        m = re.fullmatch(r"\[\s*IMG\s*(\d+)\s*\]", b.strip(), re.I)
        if m and int(m.group(1)) in figures:
            blocks[i] = figures[int(m.group(1))]
            placed.append(int(m.group(1)))
    # 2) explicit rules
    for r in rules:
        if r.n in placed:
            continue
        for i, b in enumerate(blocks):
            hit = (r.mode == "after-heading" and b.startswith("#") and r.needle.lower() in b.lower()) or (
                r.mode == "after-text" and not b.startswith("#") and b.lower().lstrip("*> ").startswith(r.needle.lower())
            )
            if hit:
                blocks.insert(i + 1, figures[r.n])
                placed.append(r.n)
                break
        else:
            raise SystemExit(f"--place {r.n}: no block matched '{r.needle}'")
    return "\n\n".join(blocks) + "\n", placed


# ---------------------------------------------------------------- front matter
def yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_post(*, slug, title, description, date, category, feature: ImageMeta, feature_alt, body) -> Path:
    fm = [
        "---",
        f"title: {yaml_str(title)}",
        f"description: {yaml_str(description)}",
        f"date: {date}",
        f"category: {category}",
        "feature:",
        f"  name: {feature.name}",
        f"  alt: {yaml_str(feature_alt)}",
        f"  w: {feature.w}",
        f"  h: {feature.h}",
        f"image: /blog/images/{slug}/{feature.name}-og.jpg",
        "---",
        "",
    ]
    path = POSTS / f"{date[:10]}-{slug}.md"
    path.write_text("\n".join(fm) + "\n" + clean_text(body), encoding="utf-8")
    return path


# ---------------------------------------------------------------- check
def categories() -> set[str]:
    return {p.stem for p in CATS.glob("*.md")}


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    data: dict = {}
    parent = None
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  ") and parent:
            k, _, v = line.strip().partition(":")
            data[parent][k.strip()] = v.strip().strip('"')
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v == "":
            data[k] = {}
            parent = k
        else:
            data[k] = v.strip('"')
            parent = None
    return data, m.group(2)


def check_post(path: Path) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    if INVISIBLE_RE.search(text):
        problems.append("contains invisible Unicode characters")
    fm, body = parse_front_matter(text)
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$", path.name)
    if not m:
        return problems + ["filename must be YYYY-MM-DD-<slug>.md"]
    slug = m.group(2)
    if not SLUG_RE.match(slug):
        problems.append(f"slug '{slug}' must be lowercase-kebab")
    for key in ("title", "description", "date", "category", "feature", "image"):
        if not fm.get(key):
            problems.append(f"missing front matter: {key}")
    if fm.get("category") and fm["category"] not in categories():
        problems.append(f"category '{fm['category']}' not in _blog_categories/ ({', '.join(sorted(categories()))})")
    d = fm.get("description", "")
    if d and not (50 <= len(d) <= 200):
        problems.append(f"description is {len(d)} chars (aim for 120-160)")
    feat = fm.get("feature") or {}
    for k in ("name", "alt", "w", "h"):
        if isinstance(feat, dict) and not feat.get(k):
            problems.append(f"feature.{k} missing")
    names = []
    if isinstance(feat, dict) and feat.get("name"):
        names.append((feat["name"], feat.get("alt", "x")))
        og = ROOT / fm.get("image", "").lstrip("/")
        if not og.is_file():
            problems.append(f"OG image missing: {fm.get('image')}")
    for args in FIG_RE.findall(body):
        kv = {k: (q or u) for k, q, u in re.findall(r'(\w+)=(?:"([^"]*)"|(\S+))', args)}
        if not kv.get("name"):
            problems.append(f"figure without name: {args.strip()}")
            continue
        for k in ("alt", "w", "h"):
            if not kv.get(k):
                problems.append(f"figure '{kv['name']}' missing {k}")
        names.append((kv["name"], kv.get("alt", "x")))
    for name, _alt in names:
        for w in WIDTHS:
            f = IMAGES / slug / f"{name}-{w}.webp"
            if not f.is_file():
                problems.append(f"missing image {f.relative_to(ROOT)}")
    return problems


def cmd_check(_args) -> int:
    bad = 0
    posts = sorted(POSTS.glob("*.md"))
    for p in posts:
        probs = check_post(p)
        print(("FAIL " if probs else "ok   ") + str(p.relative_to(ROOT)))
        for pr in probs:
            print("     - " + pr)
        bad += bool(probs)
    print(f"{len(posts)} post(s), {bad} with problems")
    return 1 if bad else 0


# ---------------------------------------------------------------- commands
def cmd_image(a) -> int:
    meta = optimize_image(Path(a.src), a.slug, a.name, og=a.og)
    print(f"name={meta.name} w={meta.w} h={meta.h}")
    return 0


def cmd_post(a) -> int:
    if not SLUG_RE.match(a.slug):
        raise SystemExit("slug must be lowercase-kebab")
    if a.category not in categories():
        raise SystemExit(f"unknown category; choose one of {sorted(categories())}")
    md = docx_to_markdown(Path(a.docx))
    title = a.title
    if not title:
        m = re.match(r"^# (.+)\n", md)
        if not m:
            raise SystemExit("no Heading 1 in the docx; pass --title")
        title = m.group(1).strip()
    md = re.sub(r"^# .+\n+", "", md, count=1)  # title goes to front matter, not the body
    md = re.sub(r"^#### ", "### ", md, flags=re.M)
    img_dir = Path(a.images)
    feature = optimize_image(img_dir / a.feature, a.slug, "feature", og=True)
    alts = dict(s.split("=", 1) for s in a.alt)  # "3=Crawl depth chart"
    caps = dict(s.split("=", 1) for s in a.caption)
    figures: dict[int, str] = {}
    files = sorted(p for p in img_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".heic") and p.name != a.feature)
    for p in files:
        m = re.match(r"^(\d+)", p.stem)
        if not m:
            continue
        n = int(m.group(1))
        meta = optimize_image(p, a.slug, f"{n:02d}")
        alt = alts.get(str(n)) or re.sub(r"[-_]+", " ", p.stem.split("-", 1)[-1] if "-" in p.stem else f"Image {n}").strip()
        figures[n] = figure_tag(meta, alt, caps.get(str(n), ""), wide=str(n) in a.wide)
    body, placed = place_figures(md, figures, [parse_place(s) for s in a.place])
    unplaced = sorted(set(figures) - set(placed))
    date = a.date or dt.date.today().isoformat()
    if len(date) == 10:
        date += " 09:00:00 +0100"
    desc = a.description or re.sub(r"[*_\[\]]|\(http[^)]*\)", "", next(b for b in body.split("\n\n") if b and not b.startswith(("#", "{%")))).strip()[:157]
    path = write_post(slug=a.slug, title=title, description=desc, date=date, category=a.category,
                      feature=feature, feature_alt=a.feature_alt or title, body=body)
    words = len(re.sub(r"\{%.*?%\}", "", body).split())
    print(f"wrote {path.relative_to(ROOT)}  ({words} words, ~{max(1, -(-words // 220))} min)")
    print("headings:", [h for h in re.findall(r"^#{2,3} (.+)$", body, re.M)])
    if unplaced:
        print("WARNING unplaced images:", unplaced)
    missing_alt = [n for n in figures if str(n) not in alts]
    if missing_alt:
        print("WARNING alt text guessed from filename for images:", missing_alt, "(pass --alt N=\"...\")")
    probs = check_post(path)
    for pr in probs:
        print("CHECK", pr)
    return 1 if probs else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("image", help="optimize one image")
    i.add_argument("src"); i.add_argument("--slug", required=True); i.add_argument("--name", required=True)
    i.add_argument("--og", action="store_true", help="also write <name>-og.jpg (1200x630)")
    i.set_defaults(fn=cmd_image)
    p = sub.add_parser("post", help="docx + images -> post")
    p.add_argument("--docx", required=True); p.add_argument("--images", required=True)
    p.add_argument("--slug", required=True); p.add_argument("--category", required=True)
    p.add_argument("--feature", required=True, help="feature image filename inside --images")
    p.add_argument("--feature-alt"); p.add_argument("--title"); p.add_argument("--description")
    p.add_argument("--date", help="YYYY-MM-DD or full 'YYYY-MM-DD HH:MM:SS +0100'")
    p.add_argument("--place", action="append", default=[], help="N:after-text=... | N:after-heading=...")
    p.add_argument("--alt", action="append", default=[], help='N=alt text')
    p.add_argument("--caption", action="append", default=[], help='N=caption')
    p.add_argument("--wide", action="append", default=[], help="N (image breaks out of the text column)")
    p.set_defaults(fn=cmd_post)
    c = sub.add_parser("check", help="validate all posts")
    c.set_defaults(fn=cmd_check)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
