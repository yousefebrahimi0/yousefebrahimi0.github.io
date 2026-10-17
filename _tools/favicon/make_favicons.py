#!/usr/bin/env python3
"""Build the yousef.uk favicon set from one square-ish source image and wire it into the site.

Usage (from the repo root):
  python3 _tools/favicon/make_favicons.py /workspace/uploads/yousef.png            # generate + patch heads
  python3 _tools/favicon/make_favicons.py SRC --version 4 --bg "#111111"         # custom cache-bust / iOS background
  python3 _tools/favicon/make_favicons.py SRC --no-patch                         # only generate files

Outputs in assets/icon/:
  favicon.ico (16, 32, 48), favicon-16x16.png, favicon-32x32.png,
  apple-touch-icon.png (180, flattened on --bg, since iOS ignores transparency),
  android-chrome-192x192.png, android-chrome-512x512.png, site.webmanifest
--small-crop LEFT,TOP,SIZE uses a tighter crop for the tiny sizes (16/32/48) so a face stays recognisable.
Patches the <!-- favicons --> block in index.html and _includes/blog/head.html (idempotent).
"""
import argparse, json, re, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "icon"
HEADS = [ROOT / "index.html", ROOT / "_includes" / "blog" / "head.html"]

def square(img):
    img = img.convert("RGBA")
    w, h = img.size
    s = min(w, h)
    return img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))

def resized(img, n):
    return img.resize((n, n), Image.LANCZOS)

def tags(v, indent):
    lines = [
        "<!-- favicons -->",
        f'<link rel="icon" href="/assets/icon/favicon.ico?v={v}" sizes="48x48">',
        f'<link rel="icon" type="image/png" sizes="32x32" href="/assets/icon/favicon-32x32.png?v={v}">',
        f'<link rel="icon" type="image/png" sizes="16x16" href="/assets/icon/favicon-16x16.png?v={v}">',
        f'<link rel="apple-touch-icon" sizes="180x180" href="/assets/icon/apple-touch-icon.png?v={v}">',
        f'<link rel="manifest" href="/site.webmanifest?v={v}">',
        "<!-- /favicons -->",
    ]
    return "\n".join(indent + l for l in lines)

def patch(path, v):
    s = path.read_text()
    indent = "  " if path.name == "index.html" else ""
    block = tags(v, indent)
    if "<!-- favicons -->" in s:
        s = re.sub(r"[ \t]*<!-- favicons -->.*?<!-- /favicons -->", block, s, flags=re.S)
    else:
        old = re.compile(r'[ \t]*<link rel="(?:shortcut )?icon" href="[^"]*favicon\.ico"[^>]*>')
        if not old.search(s):
            sys.exit(f"no favicon tag or marker found in {path}")
        s = old.sub(lambda m: block, s, count=1)
    path.write_text(s)
    print("patched", path.relative_to(ROOT))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--version", default="3")
    ap.add_argument("--bg", default="#111111", help="background for apple-touch-icon")
    ap.add_argument("--no-patch", action="store_true")
    ap.add_argument("--small-crop", help="LEFT,TOP,SIZE box (source px) used for the 16/32/48 icons, e.g. a crop centred on the face")
    a = ap.parse_args()
    src = square(Image.open(a.src))
    if src.size[0] < 512:
        print(f"warning: source is {src.size[0]}px; 512px+ recommended", file=sys.stderr)
    OUT.mkdir(parents=True, exist_ok=True)
    small = src
    if a.small_crop:
        l, t, n = (int(x) for x in a.small_crop.split(","))
        small = Image.open(a.src).convert("RGBA").crop((l, t, l + n, t + n))
    resized(small, 48).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    for n in (16, 32):
        resized(small, n).save(OUT / f"favicon-{n}x{n}.png", optimize=True)
    for n in (192, 512):
        resized(src, n).save(OUT / f"android-chrome-{n}x{n}.png", optimize=True)
    bg = Image.new("RGBA", (180, 180), a.bg)
    bg.alpha_composite(resized(src, 180))
    bg.convert("RGB").save(OUT / "apple-touch-icon.png", optimize=True)
    manifest = {
        "name": "Yousef Ebrahimi", "short_name": "Yousef",
        "icons": [
            {"src": f"/assets/icon/android-chrome-192x192.png?v={a.version}", "sizes": "192x192", "type": "image/png"},
            {"src": f"/assets/icon/android-chrome-512x512.png?v={a.version}", "sizes": "512x512", "type": "image/png"},
        ],
        "theme_color": "#111111", "background_color": "#111111", "display": "browser", "start_url": "/",
    }
    (ROOT / "site.webmanifest").write_text(json.dumps(manifest, indent=2) + "\n")
    print("wrote icons to", OUT.relative_to(ROOT), "and site.webmanifest")
    if not a.no_patch:
        for h in HEADS:
            patch(h, a.version)

if __name__ == "__main__":
    main()
