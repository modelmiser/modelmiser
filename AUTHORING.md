# Authoring Guide — modelmiser.com

Reference for writing and deploying blog posts. Read this before creating content.

## Voice

See `editorial_voice.md` for the full personality. Summary:

- **Stevens' rigor + Ganssle's warmth** — colleague to colleague
- **Blog posts are arguments, not tutorials** — thesis, evidence, implications
- **No** "Try It" checkpoints, exercises, or learning objectives
- **No** "In this post I will..." or "In conclusion..."
- Every sentence pulls its weight. No padding.

## Post Structure

```
docs/blog/posts/<slug>.md
```

### Frontmatter

```yaml
---
date: YYYY-MM-DD
---
```

### Required Elements

1. **Title** — `# Title` as first content line
2. **Subtitle** — one line below the title, before `<!-- more -->`
3. **Excerpt separator** — `<!-- more -->` after the subtitle (the blog plugin uses this for the index page)
4. **Sections** — `##` headings, no deeper than `###`
5. **Footer** — project status + repo link, separated by `---`

### Template

```markdown
---
date: 2026-04-15
---

# Post Title Here

One-line subtitle that captures the insight.

<!-- more -->

## First section

Content...

## Second section

Content...

---

*Project description. [GitHub](https://github.com/modelmiser/repo).*
```

## Code Blocks

**Always tag the language.** Untagged fences get no syntax highlighting.

| Content | Tag |
|---------|-----|
| C / pseudocode | `c` |
| Rust | `rust` |
| Verilog | `verilog` |
| Assembly | `asm` |
| Plain text / traces | `text` |
| Diagrams | `mermaid` |

## Mermaid Diagrams

One good diagram per post is typical. Three means you're writing a tutorial.
Use for state machines, pipeline stages, data flow — things prose can't
communicate. Don't use for simple lists or hierarchies.

## Content Rules

### Accuracy

- **No price claims on hardware.** ULX3S price varies $85-$250 by region.
  Say "hobbyist FPGA board" not "$50 board."
- **Project lineage matters.** warp-types (type theory) came before warp-core
  (hardware). The formal work informed the ISA design, not the reverse.
- **Concrete numbers.** LUTs, cycles, bytes, latencies — always include them
  when making claims about cost or performance.
- **Verify external claims.** Don't state things about other projects (NVIDIA,
  AMD, RISC-V) without checking. The cold-review protocol applies to blog
  posts too.

### What not to write

- Fabricated experience
- Empty praise ("elegant", "beautiful")
- Hedging on opinions the evidence supports
- Bullet-point lists where prose would flow better
- Generic introductions or conclusions

## The Devlog-to-Blog Pipeline

Each post originates from DEVLOG.md "interesting problem" sections.

**Devlog → Blog transformation:**
- Add context a stranger needs (what is SIMT, why does divergence matter)
- Remove session artifacts (round numbers, commit hashes, skill names)
- Shape the reasoning into an argument with a thesis
- One devlog entry = one blog post (sometimes 2-3 entries combine into one)

**Three narrative arcs identified (Mar-Apr 2026):**
1. Auto-diverging branches (shipped)
2. Constraints as features — how 4K IMEM became the design
3. The CSR space as an extension mechanism

## Typography & Styling

All style lives in `docs/stylesheets/blog.css`. Key decisions:

| Property | Value | Reason |
|----------|-------|--------|
| Font | Segoe UI (system stack) | User preference; no Google Fonts load |
| Code font | Cascadia Code → JetBrains Mono → Fira Code | Segoe UI companion |
| Body size | 0.85rem | Tighter than Material default |
| Line height | 1.7 | Generous for readability |
| Content width | 48rem max | Optimal line length for long-form |
| Color scheme | Dark default (slate) | User preference |
| Right sidebar | Hidden | Blog posts don't need a TOC sidebar |

## Site Structure

```
modelmiser/                    ← GitHub profile repo + site source
├── README.md                  ← GitHub profile (rendered on github.com/modelmiser)
├── mkdocs.yml                 ← Site config
├── editorial_voice.md         ← Full voice reference
├── AUTHORING.md               ← This file
├── requirements.txt           ← mkdocs-material, mkdocs-mermaid2-plugin
├── vercel.json                ← Build config for Vercel
├── overrides/main.html        ← Theme override shell
├── docs/
│   ├── index.md               ← Landing page (logo + links)
│   ├── assets/logo.jpeg       ← Bison silhouette
│   ├── stylesheets/blog.css   ← Blog typography
│   ├── blog/
│   │   ├── index.md           ← Blog index (auto-populated by plugin)
│   │   └── posts/             ← Blog posts (one .md per post)
│   └── projects/              ← Research project pages
```

## Local Preview

```bash
cd /path/to/modelmiser
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/mkdocs serve -a localhost:8001
```

Note: `mkdocs serve` may not pick up external file edits (e.g., from Claude
Code). Restart the server if changes don't appear after a hard refresh.

## Deployment

**Vercel** handles deployment. The domain modelmiser.com is already configured.

| Trigger | Result |
|---------|--------|
| Push to any branch | Vercel preview URL (staging) |
| Push to main | Live at modelmiser.com |

**Staging workflow:**
1. Write/edit in a branch
2. `mkdocs serve` locally for fast iteration
3. Push branch → Vercel preview URL for cold review
4. Merge to main → live

## Nav Tabs

| Tab | Content |
|-----|---------|
| Home | Landing page with logo, blog links, research links |
| Blog | Auto-generated index with post excerpts |
| Research | Project pages (warp-core, warp-types) |
