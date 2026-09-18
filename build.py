# /// script
# requires-python = ">=3.12"
# dependencies = ["markdown>=3.7", "jinja2>=3.1", "pyyaml>=6.0"]
# ///
"""Build the Cold Admission campaign site into docs/ for GitHub Pages.

    uv run build.py

Content lives in content/ as markdown with YAML frontmatter. Each file may have an
.es.md sibling holding the Spanish body; structural frontmatter is never duplicated.
"""

import re
import shutil
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
DOCS = ROOT / "docs"
LANGS = ["en", "es"]
LANG_ATTR = {"en": "en", "es": "es-MX"}

MD = markdown.Markdown(extensions=["tables", "attr_list", "sane_lists", "toc"])

# [REDACTED:Justin] -> revealable bar; bare [REDACTED]/[REDACTADO] -> permanent bar.
RE_REVEAL = re.compile(r"\[(?:REDACTED|REDACTADO):([^\]]+)\]")
RE_BAR = re.compile(r"\[(?:REDACTED|REDACTADO)\]")


def split_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body.lstrip("\n")


def redact(html):
    html = RE_REVEAL.sub(
        lambda m: f'<span class="redacted revealable" tabindex="0" role="button">'
        f'{m.group(1)}</span>',
        html,
    )
    return RE_BAR.sub('<span class="redacted"></span>', html)


# "(Section 4)" / "(Sección 4)" — dead text on a page, so point them at the heading.
RE_XREF = re.compile(r"\((Section|Secci\u00f3n)\s+(\d+)\)")
RE_H2_NUM = re.compile(r'<h2 id="([^"]+)">\s*(\d+)\.')


def linkify_sections(html):
    ids = {num: hid for hid, num in RE_H2_NUM.findall(html)}
    # A reference with no matching heading stays plain text rather than dead-linking.
    return RE_XREF.sub(
        lambda m: (f'(<a class="xref" href="#{ids[m.group(2)]}">{m.group(1)} {m.group(2)}</a>)'
                   if m.group(2) in ids else m.group(0)),
        html,
    )


def render_md(body):
    MD.reset()
    return linkify_sections(redact(MD.convert(body)))


def load(path):
    """Return (meta, {lang: html}). meta comes from the base file only."""
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    meta["slug"] = path.stem
    bodies = {"en": render_md(body)}

    es_path = path.with_suffix(".es.md")
    if es_path.exists():
        es_meta, es_body = split_frontmatter(es_path.read_text(encoding="utf-8"))
        bodies["es"] = render_md(es_body)
        # Only prose-bearing fields may be overridden.
        for key in ("tagline", "cell_status", "cover", "agency", "outcome",
                    "injuries", "bonds", "disorders", "threads"):
            if key in es_meta:
                meta.setdefault("es", {})[key] = es_meta[key]
    else:
        bodies["es"] = None  # falls back to English, flagged in the template
    return meta, bodies


def localized(meta, lang):
    """Merge the .es.md frontmatter overrides over the base meta for this language."""
    if lang == "es" and "es" in meta:
        return {**meta, **meta["es"]}
    return meta


def main():
    strings = yaml.safe_load((CONTENT / "strings.yml").read_text(encoding="utf-8"))

    cell_meta, cell_bodies = load(CONTENT / "cell.md")
    agents = [load(p) for p in sorted(CONTENT.glob("agents/*.md")) if not p.name.endswith(".es.md")]
    ops = [load(p) for p in sorted(CONTENT.glob("operations/*.md")) if not p.name.endswith(".es.md")]
    ops.reverse()  # newest operation first

    # Maps are optional: a non-empty per-operation folder renders a plates section.
    for meta, _ in ops:
        folder = ROOT / "assets" / "maps" / meta["slug"]
        meta["maps"] = sorted(p.name for p in folder.glob("*") if p.suffix.lower() in
                              {".jpg", ".jpeg", ".png", ".webp", ".gif"}) if folder.is_dir() else []

    # Open threads live on operations; the cover sheet aggregates them.
    order = {"hot": 0, "warm": 1, "cold": 2}
    threads = [
        {**t, "op": meta["slug"], "op_title": meta.get("title", "")}
        for meta, _ in ops
        for t in (meta.get("threads") or [])
    ]
    threads.sort(key=lambda t: order.get(t.get("level", "cold"), 3))

    by_slug = {m["slug"]: m for m, _ in agents}

    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # Frontmatter strings carry redaction markers too, not just markdown bodies.
    env.filters["redact"] = lambda v: Markup(redact(str(escape(v))))

    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()
    (DOCS / ".nojekyll").touch()
    shutil.copytree(ROOT / "assets", DOCS / "assets")
    shutil.copytree(ROOT / "static", DOCS / "static")

    def write(rel, template, lang, **ctx):
        base = DOCS if lang == "en" else DOCS / "es"
        out = base / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        # Depth from this page back to the language root, then out to the site root.
        depth = len(Path(rel).parts) - 1
        up = "../" * depth
        site_root = "../" * (depth + (0 if lang == "en" else 1))
        # Same page in the other language, not that language's home page.
        alt_url = site_root + ("es/" if lang == "en" else "") + rel.rsplit("index.html", 1)[0]
        out.write_text(
            env.get_template(template).render(
                lang=lang,
                lang_attr=LANG_ATTR[lang],
                t=strings[lang],
                root=up or "./",
                site_root=site_root or "./",
                alt_url=alt_url or "./",
                alt_lang="es" if lang == "en" else "en",
                threads=threads,
                agents=[localized(m, lang) for m, _ in agents],
                operations=[localized(m, lang) for m, _ in ops],
                **ctx,
            ),
            encoding="utf-8",
        )

    for lang in LANGS:
        write("index.html", "index.html.j2", lang,
              page=localized(cell_meta, lang),
              body=cell_bodies[lang] or cell_bodies["en"],
              untranslated=cell_bodies[lang] is None)

        write("agents/index.html", "roster.html.j2", lang)
        for meta, bodies in agents:
            write(f"agents/{meta['slug']}/index.html", "agent.html.j2", lang,
                  page=localized(meta, lang),
                  body=bodies[lang] or bodies["en"],
                  untranslated=bodies[lang] is None)

        write("operations/index.html", "operations.html.j2", lang)
        for meta, bodies in ops:
            write(f"operations/{meta['slug']}/index.html", "operation.html.j2", lang,
                  page=localized(meta, lang),
                  body=bodies[lang] or bodies["en"],
                  untranslated=bodies[lang] is None,
                  roster=[localized(by_slug[s], lang) for s in meta.get("roster", [])
                          if s in by_slug])

    pages = sum(1 for _ in DOCS.rglob("*.html"))
    print(f"built {pages} pages -> {DOCS}")


if __name__ == "__main__":
    main()
