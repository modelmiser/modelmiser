"""
mkdocs hook: auto-populate the landing page Writing section from blog posts.

Replaces <!-- blog-recent --> in index.md with a generated list of all posts,
sorted newest-first, with { .crossdomain } attribute for posts in that category.

Post format expected:
    ---
    date: YYYY-MM-DD
    categories:        # optional
      - crossdomain
    ---
    # Title
    Subtitle line.
    <!-- more -->
"""

import os
import re

POSTS_DIR = os.path.join("docs", "blog", "posts")
PLACEHOLDER = "<!-- blog-recent -->"


def _parse_post(filepath):
    """Extract date, title, subtitle, categories from a blog post."""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # Parse YAML frontmatter (between --- delimiters)
    fm_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not fm_match:
        return None
    frontmatter = fm_match.group(1)

    # Date (with optional time for same-day ordering)
    date_match = re.search(
        r"^date:\s*(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}:\d{2}))?",
        frontmatter,
        re.MULTILINE,
    )
    if not date_match:
        return None
    date = date_match.group(1)
    time = date_match.group(2) or "00:00:00"
    sort_key = f"{date} {time}"

    # Categories
    categories = []
    cat_match = re.search(
        r"^categories:\s*\n((?:\s+-\s+\S+\n?)+)", frontmatter, re.MULTILINE
    )
    if cat_match:
        categories = re.findall(r"-\s+(\S+)", cat_match.group(1))

    # Body after frontmatter
    body = content[fm_match.end():]

    # Title: first # heading
    title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if not title_match:
        return None
    title = title_match.group(1).strip()

    # Subtitle: line between title and <!-- more -->
    after_title = body[title_match.end():].strip()
    subtitle = ""
    for line in after_title.split("\n"):
        line = line.strip()
        if line == "<!-- more -->":
            break
        if line:
            subtitle = line
            break

    slug = os.path.splitext(os.path.basename(filepath))[0]

    return {
        "date": date,
        "sort_key": sort_key,
        "title": title,
        "subtitle": subtitle,
        "categories": categories,
        "slug": slug,
    }


def _build_writing_list(posts):
    """Generate markdown list from parsed posts."""
    lines = []
    for post in posts:
        link = f"blog/posts/{post['slug']}.md"
        crossdomain = "crossdomain" in post["categories"]
        attr = "{ .crossdomain }" if crossdomain else ""

        entry = f"- [**{post['title']}**]({link}){attr}"
        if post["subtitle"]:
            # Lowercase first char of subtitle for "— subtitle" flow
            sub = post["subtitle"]
            sub_lower = sub[0].lower() + sub[1:] if sub else sub
            # Strip trailing period if present
            if sub_lower.endswith("."):
                sub_lower = sub_lower[:-1]
            entry += f" — {sub_lower}"

        lines.append(entry)

    return "\n".join(lines)


def on_page_markdown(markdown, page, config, files, **kwargs):
    """Replace <!-- blog-recent --> placeholder with auto-generated post list."""
    if page.file.src_path != "index.md":
        return markdown
    if PLACEHOLDER not in markdown:
        return markdown

    # Find and parse all posts
    posts_path = os.path.join(config["docs_dir"], "blog", "posts")
    if not os.path.isdir(posts_path):
        return markdown

    posts = []
    for filename in os.listdir(posts_path):
        if not filename.endswith(".md"):
            continue
        parsed = _parse_post(os.path.join(posts_path, filename))
        if parsed:
            posts.append(parsed)

    # Sort by date+time descending (newest first, highest time first within same day)
    posts.sort(key=lambda p: p["sort_key"], reverse=True)

    writing_list = _build_writing_list(posts)
    return markdown.replace(PLACEHOLDER, writing_list)
