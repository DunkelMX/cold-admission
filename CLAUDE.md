# CLAUDE.md — Cold Admission campaign site

Static bilingual site for a Delta Green cell's records. Live at
https://dunkelmx.github.io/cold-admission/ — GitHub Pages serves `/docs` from `main`.

`README.md` covers the mechanics (how to add a session, what each folder is). This file
covers the **conventions and the traps** — the things that are not obvious from reading
the code, and the ones that have already cost a rebuild.

## Naming: campaign vs operation

**Cold Admission is the campaign.** Operations inside it have their own names and their
own posters — Operation 01 is **Gutter Key**. Keep the two levels distinct everywhere:

- site chrome and the cover sheet carry the campaign
- operation pages carry the operation, and never borrow the campaign poster or tagline
- **titles are brand names and are never translated** — not "Ingreso en frío"

## The redaction system

Two classes, both in `build.py`'s `redact()`:

| Marker | Renders as |
|---|---|
| `[REDACTED]` | permanent empty bar, nothing to reveal |
| `[REDACTED:text]` | bar holding real text — readable by selecting, hovering, or clicking |

Works in markdown bodies **and** in frontmatter strings (via the `redact` Jinja filter).

Three rules, all learned the hard way:

1. **Visible prose must name nothing.** "A portal-like ███" is a failure: it names the
   phenomenon in the clear and hides a neutral synonym. Censor the whole naming.
2. **The hidden text is the payoff.** A bar that opens to reveal the word "aperture" is
   not worth a bar. It should open to *"what looked like an interdimensional portal"*.
3. **Every sentence must read correctly in both states.** Where revealing would leave a
   dangling appositive, put the closing punctuation *inside* the bar — hidden when
   closed, correct when open.

Never redact something the text contradicts elsewhere. §6 cannot hide a facility name,
because TRIAGE says two paragraphs later he was never given one — it hides a
description of the room instead.

Censored vocabulary is fixed in `glossary.yml` → `redaction_terms`. Recurring phrases
beat unique ones: a man reaching for the same inadequate words reads truer.

## Voice

TRIAGE is a field medic writing a report. Clipped, clinical, first person, hedged —
*what looked like*, *or what functioned as*, *I have no medical basis on which to*.
The horror arrives inside his qualifications, never as purple prose. Clinical detail
stays precise (*otorragia bilateral*, *haloperidol 2 mg IM*).

Invented content carries `provisional: true`, which stamps the dossier. Anything the
after-action report actually says stays accurate; everything else is replaceable.

## Spanish — es-MX, never Peninsular

`glossary.yml` is authoritative and goes into the translator's system prompt on every
call. The essentials:

- `ustedes`, never `vosotros`; simple preterite, not compound perfect
- **`coger` is banned in every form** — vulgar in Mexico, and the English source is full
  of *seized* / *grabbed* / *took*. `translate.py` refuses to write output containing it
- Mexican lexicon: *carro*, *estacionamiento*, *manejar*, *celular*, *banqueta*
- published Spanish DG/CoC terms: *Cordura*, *Vínculos*, *Trastornos*, *Lo Paranormal*

**Redaction markers are copied verbatim by the model and substituted mechanically from
`redaction_terms`.** This is deliberate — when the model was allowed to translate them
itself, its wording drifted between runs and the map (keyed on English) could never
match. Do not "improve" this by asking the model to translate them.

## Traps

- **uv's bundled CPython cannot resolve DNS on this host** — it doesn't support the
  `mdns_minimal` / `resolve` NSS modules in `/etc/nsswitch.conf`. `translate.py` pins
  itself to the system Python via `[tool.uv] python-preference = "only-system"`. Don't
  remove that. `build.py` needs no network.
- **Hand-editing an English body invalidates `source_sha`.** Either resync the hash
  after mirroring the edit in Spanish, or delete the `.es.md` and regenerate. Otherwise
  the next `translate.py` silently re-translates over your edits.
- **The frontmatter translation pass can fabricate.** It once invented an operation,
  a second aperture and a site name. A key-set guard in `translate.py` discards any
  reply whose keys don't match what was sent — keep it.
- **Don't pipe `translate.py` through `head`** — SIGPIPE kills it mid-run, after it has
  already written some files and updated their hashes.
- **`build.py` wipes `docs/` every run.** Never hand-edit anything in there.
- **An asset folder git-removed to empty disappears.** `mkdir -p` before writing into
  `assets/keyart/`.
- **Generated images arrive as PNG named `.jpg`, often multi-MB.** Check with
  `identify` and re-encode: `magick in.jpg -resize 1200x1600 -strip -quality 82 out.jpg`.
  1200×1600 is the poster standard.
- **Posters already contain their own title typography.** Don't overlay a second title
  on them; frame them as a plate instead.

## Verify before shipping

These have each caught a real bug:

```bash
# 1. nothing named in the clear: strip the bars, then look for the censored words
python3 -c "
import re
h = open('docs/operations/01-gutter-key/index.html').read()
b = re.sub(r'<[^>]+>', ' ', re.sub(r'<span class=\"redacted[^>]*>[^<]*</span>', '', h))
print([w for w in ['portal','aperture','entity','tentacle','anomaly']
       if re.search(rf'\b{w}', b, re.I)] or 'NONE')"

# 2. bar counts must match across languages
grep -c 'redacted revealable' docs/operations/01-gutter-key/index.html \
                              docs/es/operations/01-gutter-key/index.html

# 3. hashes settled — no silent re-translation pending
uv run translate.py --dry-run     # must say "nothing to translate"
```

Plus: read the revealed text for grammar, click a cross-reference in each language,
check no horizontal scroll at 400px, and screenshot both languages before committing.
