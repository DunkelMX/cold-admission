# /// script
# requires-python = ">=3.12"
# dependencies = ["anthropic>=1.0.0", "pyyaml>=6.0", "python-dotenv>=1.0"]
#
# [tool.uv]
# # uv's bundled CPython can't use this host's NSS resolver modules (mdns_minimal /
# # resolve in /etc/nsswitch.conf), so DNS fails inside it. Use the system Python.
# python-preference = "only-system"
# ///
"""Generate the Spanish (es-MX) siblings of the campaign content.

    uv run translate.py [--dry-run] [--force]

For every content/**/*.md it writes a .es.md sibling, skipping files whose English
body hasn't changed since the last run (tracked by source_sha) and files marked
locked: true. Terminology and register come from glossary.yml, so the Spanish stays
consistent — and stays Mexican — across sessions.
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

import anthropic
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
MODEL = "claude-opus-5"

# Prose-bearing frontmatter keys worth translating; everything else is structural.
# "title" is deliberately absent: operation and campaign titles are brand names that
# stay in English. Thread "level" values are structural too — they key CSS classes and
# string lookups — so threads are translated as bare text and re-paired below.
TRANSLATABLE_KEYS = ("tagline", "cell_status", "cover", "agency", "outcome",
                     "injuries", "bonds", "disorders")


def split_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body.lstrip("\n")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def system_prompt(glossary):
    terms = "\n".join(f"  {en}  ->  {es}" for en, es in glossary["terms"].items())
    rules = "\n".join(f"  - {r}" for r in glossary["rules"])
    banned = ", ".join(glossary["banned"])
    never = "\n".join(f"  - {n}" for n in glossary.get("never_translate", []))
    return f"""You translate Delta Green campaign records from English into \
{glossary['variant_name']} ({glossary['variant']}).

These are in-fiction after-action reports and personnel dossiers written by a federal \
field medic. The register is military and clinical: clipped, declarative, precise. \
Translate the meaning and the voice, not the words.

FIXED TERMINOLOGY — use these renderings exactly:
{terms}

RULES:
{rules}

NEVER TRANSLATE:
{never}

BANNED — these words must never appear in your output in any form: {banned}
The verb "coger" is the critical one: it is vulgar in Mexico and the English source is \
full of "seized", "grabbed", "took". Use sujetar, aferrar, atrapar, tomar, or agarrar.

Return ONLY the translated markdown. No preamble, no code fences, no commentary."""


def check_banned(text, banned):
    lowered = text.lower()
    return [w for w in banned if re.search(rf"\b{re.escape(w.lower())}\b", lowered)]


def heading_count(text):
    return len(re.findall(r"^#{1,6} ", text, re.M))


def translate(client, glossary, body, extra=None):
    ask = "Translate this markdown:\n\n" + body
    if extra:
        ask = extra + "\n\n" + ask
    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        system=system_prompt(glossary),
        messages=[{"role": "user", "content": ask}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("model declined the request")
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="list what would be translated")
    ap.add_argument("--force", action="store_true", help="retranslate even if unchanged")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    glossary = yaml.safe_load((ROOT / "glossary.yml").read_text(encoding="utf-8"))

    sources = [p for p in sorted(CONTENT.rglob("*.md")) if not p.name.endswith(".es.md")]
    pending = []
    for src in sources:
        meta, body = split_frontmatter(src.read_text(encoding="utf-8"))
        dst = src.with_suffix(".es.md")
        if dst.exists():
            es_meta, _ = split_frontmatter(dst.read_text(encoding="utf-8"))
            if es_meta.get("locked"):
                print(f"  locked   {src.relative_to(ROOT)}")
                continue
            if not args.force and es_meta.get("source_sha") == sha(body):
                print(f"  current  {src.relative_to(ROOT)}")
                continue
        pending.append((src, dst, meta, body))

    if not pending:
        print("nothing to translate")
        return
    for src, *_ in pending:
        print(f"  PENDING  {src.relative_to(ROOT)}")
    if args.dry_run:
        print(f"\n{len(pending)} file(s) would be translated; nothing spent")
        return

    client = anthropic.Anthropic()
    for src, dst, meta, body in pending:
        print(f"\ntranslating {src.relative_to(ROOT)} ...", flush=True)
        out = translate(client, glossary, body)

        hits = check_banned(out, glossary["banned"])
        if hits:
            print(f"  banned terms {hits} — retrying once")
            out = translate(client, glossary, body,
                            extra=f"Your previous attempt used these banned words: "
                                  f"{', '.join(hits)}. They are forbidden. Rewrite without them.")
            hits = check_banned(out, glossary["banned"])
            if hits:
                print(f"  STILL uses {hits} — not written", file=sys.stderr)
                continue

        if heading_count(out) != heading_count(body):
            print(f"  heading count {heading_count(out)} != {heading_count(body)} "
                  f"— not written", file=sys.stderr)
            continue

        # Translate the prose-bearing frontmatter fields in one extra pass.
        subset = {k: meta[k] for k in TRANSLATABLE_KEYS if k in meta and meta[k]}
        if meta.get("threads"):
            subset["threads"] = [t["text"] for t in meta["threads"]]
        es_fm = {}
        if subset:
            raw = translate(client, glossary,
                            yaml.safe_dump(subset, allow_unicode=True, sort_keys=False),
                            extra="This is YAML, not prose. Translate only the string "
                                  "values; keep every key, structure and indentation "
                                  "identical. Do not add keys, do not remove keys, do "
                                  "not invent content. Return valid YAML only.")
            raw = re.sub(r"^```(?:yaml)?|```$", "", raw, flags=re.M).strip()
            try:
                es_fm = yaml.safe_load(raw) or {}
                # The frontmatter pass is the one place the model can wander off and
                # invent records. Accept it only if it returned exactly what was sent.
                if not isinstance(es_fm, dict) or set(es_fm) != set(subset):
                    print(f"  frontmatter keys {sorted(es_fm) if isinstance(es_fm, dict) else '?'} "
                          f"!= {sorted(subset)} — discarded, body only", file=sys.stderr)
                    es_fm = {}
                for k, v in list(es_fm.items()):
                    if isinstance(subset[k], list) != isinstance(v, list):
                        print(f"  frontmatter '{k}' changed shape — discarded", file=sys.stderr)
                        es_fm = {}
                        break
            except yaml.YAMLError as e:
                print(f"  frontmatter YAML failed ({e}) — body only", file=sys.stderr)
                es_fm = {}

        # Re-pair translated thread text with the untranslated structural levels.
        if meta.get("threads"):
            texts = es_fm.get("threads") or []
            if len(texts) == len(meta["threads"]):
                es_fm["threads"] = [{"level": t["level"], "text": x}
                                    for t, x in zip(meta["threads"], texts)]
            else:
                print("  thread count mismatch — threads left untranslated",
                      file=sys.stderr)
                es_fm.pop("threads", None)

        es_fm["source_sha"] = sha(body)
        dst.write_text(
            "---\n"
            + yaml.safe_dump(es_fm, allow_unicode=True, sort_keys=False)
            + "---\n\n" + out + "\n",
            encoding="utf-8",
        )
        print(f"  -> {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
