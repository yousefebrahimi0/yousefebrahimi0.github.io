# Blog authoring (yousef.uk/blog)

Everything under `_tools/` is ignored by Jekyll and never published.

## New post from a .docx
1. Joseph sends `post.docx` (Heading 1 = title, Heading 2/3 = sections) plus an image folder:
   `cover.jpg` (feature) and numbered images `1.jpg ... 5.jpg` (`1-some-name.jpg` also works).
   Easiest placement: type `[IMG 1]` ... `[IMG 5]` on their own lines in the docx.
2. Convert:
   ```bash
   python3 _tools/blog/blogtool.py post \
     --docx uploads/post.docx --images uploads/images \
     --slug my-post-slug --category data-analytics --feature cover.jpg \
     --date 2026-10-20 --description "120-160 chars for Google and cards" \
     --feature-alt "What the cover shows" \
     --alt 1="Alt text for image 1" --caption 1="Optional caption" \
     --place "2:after-heading=The audit" --place "3:after-text=When I joined" \
     --wide 4
   ```
   Output: `_posts/<date>-<slug>.md` and `blog/images/<slug>/` (WebP 480/960/1600, capped at the
   source width, metadata stripped; `feature-og.jpg` 1200x630 for social cards).
3. `python3 _tools/blog/blogtool.py check` must exit 0.
4. Preview: `bundle exec jekyll build -d /tmp/site` (github-pages gem) and screenshot before publishing.

## Rules
- Categories = files in `_blog_categories/` (slug = filename). Add a file to add a category.
- Images in posts only via `{% include blog/figure.html name=".." alt=".." w=.. h=.. %}`.
- Never reuse an image filename with different content (Cloudflare/GitHub cache it); use `-v2`.
- Slugs never change after publishing. A post dated in the future is not built until that time.
- One-off image: `python3 _tools/blog/blogtool.py image path.jpg --slug my-post --name 06`.
