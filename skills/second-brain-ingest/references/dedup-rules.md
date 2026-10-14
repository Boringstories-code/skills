# Dedup rules — merge vs append vs flag

The wiki is a **persistent compilation**, not a re-derivation. Re-ingesting an
overlapping source must strengthen existing pages, not duplicate or clobber them.

## Decision order (per extracted entity/concept)

1. **Does a page already exist for this thing?**
   - Check `00-OS/wiki/<domain>/<slug>.md` for the obvious slug.
   - Also check near-slugs and aliases (e.g. `ira` vs `roth-ira`, `usb-c` vs `usbc`).
   - If yes → **MERGE** (step 2). If no → **CREATE** from the template.

2. **MERGE — never overwrite:**
   - Append genuinely new facts as bullets under Key facts / How it works, each tagged
     `(YYYY-MM-DD source: <slug>)`.
   - Do **not** restate facts already present. Dedup at the bullet level.
   - Add the new source slug to the `sources:` array (keep `source:` = original primary).
   - Add any new `relates-to:` links and Related bullets.
   - Update `ingested:` only if you want the latest-touch date; keep `created:` fixed.

3. **CONFLICT — flag, do not resolve:**
   - If a new claim contradicts an existing one, add/extend a `## Contradictions`
     section recording both sides with provenance.
   - In `--unattended` mode also drop a `## Review needed` bullet.
   - Never silently pick a winner.

## Home + vault twins (Phase 5 specific)

BSC sources are copied with `home--` and `vault--` prefixes. When both describe the same
entity/concept:
- Produce **one canonical page** (unprefixed slug).
- `sources: [home--<slug>, vault--<slug>]`.
- If the two versions disagree on a fact → `## Contradictions` with both prefixes named.

## `--dedup-check --domain <d>` pass (no new source)

1. List every page in `00-OS/wiki/<d>/` (excluding `_index.md`, `_sources/`).
2. Group by likely-same-thing (slug similarity + alias overlap + title synonymy).
3. For each duplicate group:
   - Pick the richest page as canonical (most facts/links).
   - Merge the others' unique facts into it with provenance preserved.
   - Replace the merged-away pages with a one-line redirect stub:
     `Merged into [[canonical-slug]].` (so existing inbound wikilinks don't break).
   - Union the `sources:` arrays.
4. Log the dedup pass as one `log.md` line: `... | --dedup-check | 0 created | N updated | <d>`.

## What NOT to merge

- Different entities that happen to share a word (`Block Controller` the component vs a
  generic "controller" mention) → keep separate.
- A concept and an entity with the same name → keep separate, cross-link via `relates-to`.
