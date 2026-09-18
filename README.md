# Operation Cold Admission

Campaign record for a Delta Green cell — agent dossiers and the after-action archive,
in English and Mexican Spanish. Static site, published with GitHub Pages from `docs/`.

## Adding a session

1. Write the after-action report as markdown in `content/operations/NN-slug.md`
   (frontmatter + the report body — copy `01-gutter-key.md` as the shape).
2. `uv run translate.py` — writes the `.es.md` siblings. Skips anything unchanged.
3. `uv run build.py` — regenerates `docs/`.
4. Commit and push. Pages serves the new version.

Steps 2 and 3 need no arguments and no configuration. A new operation is one file;
the roster, the open-threads list and both language trees follow from it.

If you skip step 2, the Spanish site still works — it falls back to the English body
with a "sin traducir" bar until you translate it.

## Layout

| Path | What it is |
|---|---|
| `content/` | Everything you edit. Markdown + YAML frontmatter. |
| `content/strings.yml` | Every word of UI chrome, in both languages. |
| `glossary.yml` | Fixed EN→ES-MX terminology and the banned-word list. |
| `assets/` | Posters, portraits, maps. |
| `templates/`, `static/style.css` | Presentation. |
| `docs/` | Generated. Never edit by hand — `build.py` wipes it each run. |

## Content notes

**Redaction.** `[REDACTED]` renders as a permanent black bar. `[REDACTED:Justin]`
renders as a bar you can click to reveal the name underneath. Both work in the body
and in frontmatter strings.

**Portraits.** Drop a file in `assets/portraits/` and name it in the agent's
frontmatter (`portrait: bulwark.jpg`). Without one the dossier shows a *photo withheld*
plate. Any aspect ratio works; the CSS crops to 4:5 and applies the duotone.

**Maps.** Put images in `assets/maps/<operation-slug>/`. A non-empty folder renders a
plates section on that operation's page; an empty one renders nothing.

**Provisional dossiers.** `provisional: true` stamps the dossier as unconfirmed. The
five starting profiles are accurate wherever the Cold Admission report speaks and
invented everywhere else — delete that one line once a player supplies the real bio.

## Translation

`translate.py` calls Claude with `glossary.yml` in the system prompt, so terminology
stays fixed across sessions and stays Mexican rather than drifting to Peninsular
Spanish. It refuses to write output containing a banned term, and discards a
frontmatter reply whose keys don't match what was sent.

- `--dry-run` — list what would be translated, spend nothing.
- `--force` — retranslate everything, ignoring hashes.
- `locked: true` in a `.es.md` — you corrected it by hand; never overwrite it.

Needs `ANTHROPIC_API_KEY` in the environment or in `.env` (see `.env.example`).
`build.py` never touches the network.

> The script pins itself to the system Python: uv's bundled CPython can't use this
> host's NSS resolver modules, so DNS fails inside it.

## Publishing

Repo settings → Pages → deploy from branch `main`, folder `/docs`.
