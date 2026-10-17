# Favicon pipeline

One command turns a source image (ideally square, 512px or larger, PNG with transparency is fine) into the full icon set and wires it into both the main site and the blog:

    python3 _tools/favicon/make_favicons.py /workspace/uploads/yousef.png --version 3

- Writes `assets/icon/favicon.ico` (16/32/48), `favicon-16x16.png`, `favicon-32x32.png`, `apple-touch-icon.png` (180, flattened on `--bg`, default #111111), `android-chrome-192x192.png`, `android-chrome-512x512.png`, and `/site.webmanifest`.
- Replaces the old single favicon tag (first run) or the `<!-- favicons -->` block (later runs) in `index.html` and `_includes/blog/head.html`. Bump `--version` whenever the image changes so browsers and Cloudflare fetch the new files.
- Non-square sources are center-cropped.
- `--small-crop LEFT,TOP,SIZE` uses a tighter square (in source pixels) for the 16/32/48 sizes. For the current avatar: `--small-crop 330,250,690` (centred on the face); the 180/192/512 icons keep the full image.
