# BEREA — Django Backend

A REST API backing the Scripture Study frontend: passage lookup, concordance
data, cross references, and per-user personal notes with token-based login.

Tested with Django 6.1 / DRF 3.18.

## 1. Set up the environment

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Load the data

```bash
python manage.py migrate
python manage.py load_bible_json         # full KJV: 66 books, 31,102 verses
python manage.py load_strongs            # Strong's Greek + Hebrew lexicon
python manage.py load_tagged_greek_nt    # real per-word NT tagging (141,746 tags)
python manage.py load_tagged_hebrew_ot   # real per-word OT tagging (305,160 tags)
python manage.py load_cross_references   # 344,798 cross-references
python manage.py seed_sample_data        # demo concordance/cross-refs for 4 passages
```

**`load_bible_json`** loads the complete public-domain KJV text bundled at
`bible/fixtures/kjv/KJV_bible.json` (66 books, 31,102 verses). To load a
different translation, pass `--file` and `--translation`:

```bash
python manage.py load_bible_json --file /path/to/NIV_bible.json --translation NIV
```

The loader expects the same JSON shape as the bundled KJV file:
`{ "BookName": { "chapter": { "verse": "text" } } }`, with book names
matching `bible/book_order.py` (e.g. `"Psalm"` singular, `"1 Samuel"`,
`"Song Of Solomon"`). If a file uses different book names or nesting,
adjust the loader or the name mapping accordingly — happy to adapt it once
you share another translation's file.

**`load_strongs`** loads the full Strong's Greek (5,523 entries) and Hebrew
(8,674 entries) lexicon from `bible/fixtures/strongs/*.json` — converted
from [openscriptures/strongs](https://github.com/openscriptures/strongs).

**Important caveat on the Strong's data:** that repo is a *lexicon*
(definitions per Strong's number, e.g. "G25 = agapaō = to love") — it does
**not** tag which word in which specific verse corresponds to which
number. There's no publicly bundled file that says "the word 'loved' in
John 3:16 is G25" without a Strong's-*tagged* Bible text (a different,
larger dataset — e.g. STEPBible's TAGNT/TAHOT, or a Strong's-numbered KJV).

So `/api/strongs/` works as a **reverse lookup**, the same way the original
print Strong's Concordance does: given an English word, it searches every
lexicon entry's `kjv_def` field (how that word is rendered in the KJV) and
returns matches. This is accurate as a reference tool but isn't a
guaranteed per-verse tag — see the `note` field in that endpoint's
response.

**`seed_sample_data`** adds hand-curated concordance entries and cross
references for 4 demo passages (John 3:16-17, Romans 8:28, Psalm 23:1-3,
Genesis 1:1-3) — the verse text itself comes from the full KJV load above;
this just layers richer study data onto those specific verses, and links
each concordance entry to its full `StrongsEntry` lexicon record when one
exists. Run it *after* `load_strongs` so those links get made.

If you later get a Strong's-tagged text, `ConcordanceEntry.strongs_entry`
already has an FK to `StrongsEntry` ready to link a specific verse's word
to its exact lexicon entry at full-Bible scale.

## 3. (Optional) Create an admin user

```bash
python manage.py createsuperuser
```

Then visit `http://127.0.0.1:8000/admin/` to add/edit books, verses,
concordance entries, and cross references by hand.

## 4. Run the server

```bash
python manage.py runserver
```

The API is now live at `http://127.0.0.1:8000/api/`.

## API reference

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/passage/?book=John&chapter=3&start=16&end=17&translation=KJV&xref_limit=10` | GET | none | Verse text + curated `cross_references` + real per-word `word_tags` + votes-ranked `bulk_cross_references` (full Bible) |
| `/api/concordance/?term=loved` or `?strongs=G25` | GET | none | Search *your loaded verses'* concordance entries |
| `/api/strongs/?number=G25` | GET | none | Exact lexicon entry lookup |
| `/api/strongs/?word=loved` | GET | none | Reverse lookup across the whole 14k-entry lexicon by English word |
| `/api/auth/register/` | POST `{username, email, password}` | none | Create an account, returns a token |
| `/api/auth/login/` | POST `{username, password}` | none | Returns a token |
| `/api/auth/logout/` | POST | token | Invalidates the current token |
| `/api/notes/` | GET/POST | token | List / create the logged-in user's notes |
| `/api/notes/<id>/` | GET/PUT/DELETE | token | Manage a specific note |
| `/api/notes/by_passage/?book=John&chapter=3&start=16&end=17` | GET/PUT | token | Get-or-create the note for an exact passage; PUT `{text}` to save |

Authenticated requests need an `Authorization: Token <token>` header.

## Connecting the frontend

Open `scripture_study_application.html` in a browser. It's configured to
call `http://127.0.0.1:8000/api` (see the `API_BASE` constant near the top
of the `<script>` block) — update that if you deploy the API elsewhere.
`django-cors-headers` is set to allow all origins for development
(`CORS_ALLOW_ALL_ORIGINS = True` in `config/settings.py`); tighten this to
`CORS_ALLOWED_ORIGINS = [...]` before deploying publicly.

## Handling words with multiple meanings

There are two distinct kinds of "multiple meanings," handled differently:

**One English word → several original-language words** (e.g. "world" in
the KJV translates 6+ different Greek/Hebrew words: kosmos, aiōn, gē,
oikoumenē, etc., each with a genuinely different meaning). `/api/strongs/`
returns *all* matching candidates rather than guessing one, ranked by
`match_quality` (2 = the exact word form appears in the KJV rendering,
1 = only a stemmed root matches, 0 = weak/partial match), and flags
`"ambiguous": true` when there's more than one. This is intentional — with
only a lexicon and no verse-tagged text, there is no reliable way to know
which of the 6 words is meant at any specific verse. The endpoint surfaces
the real ambiguity instead of silently picking one.

**One Strong's number → several senses within itself** (e.g. G2889 kosmos
alone covers "decoration," "orderly arrangement," and "the world," used
literally or figuratively). Each result's `strongs_def` is also returned
pre-split into a `senses` list (split on `;`), so the UI can show distinct
meanings as separate lines instead of one run-on definition.

**Resolving ambiguity for a specific verse** ultimately requires a human
decision (or a tagged text) — that's exactly what `ConcordanceEntry` is
for. When a `ConcordanceEntry` is attached directly to a verse (as
`seed_sample_data` does for the 4 demo passages), the passage API marks it
`"confirmed_for_this_verse": true`, distinguishing a human-curated,
verse-specific mapping from the `/api/strongs/` endpoint's unresolved list
of candidates.

## Real Strong's-tagged text (word-by-word, per verse)

Everything above (`load_strongs`) is a *lexicon* — it can't tell you which
specific Greek or Hebrew word is behind "world" or "love" in a given
verse. This section adds that missing piece, for the whole Bible.

`load_tagged_greek_nt` and `load_tagged_hebrew_ot` load
[STEPBible-Data](https://github.com/STEPBible/STEPBible-Data)'s TAGNT
(Translators Amalgamated Greek NT) and TAHOT (Translators Amalgamated
Hebrew OT) files — both CC BY 4.0 — giving real word-by-word tagging of
the entire Bible, each original-language word aligned to an English gloss
and a specific Strong's number, per word, per verse. Six files are bundled
(`bible/fixtures/tagnt/` for the 2 NT files, `bible/fixtures/tahot/` for
the 4 OT files), covering all 66 books.

This resolves the ambiguity the lexicon-only approach couldn't: for
example, `/api/strongs/?word=world` returns 13 different candidate Greek
and Hebrew words (real polysemy — "world" genuinely translates that many
distinct words across the KJV). But the tagged text can say the "world" in
John 3:16 *specifically* is G2889 (kosmos), not aiōn, gē, or any of the
others — because it's tagging the actual Greek text of that actual verse,
not guessing from an English word list.

**Verified results:** 446,906 word tags loaded (141,746 NT + 305,160 OT),
98.6% linked to a `StrongsEntry` lexicon record (the remainder are
STEPBible's *extended* Strong's numbers, e.g. G6000+/H9000+, for
distinctions and grammatical particles beyond the original 1890 numbering
— not a data error). Verse coverage: **100.0% of OT** (23,145/23,145) and
**99.9% of NT** (7,949/7,957) have at least one tag.

The NT's 8 untagged verses (John 7:53, Romans 16:25-27, 2 Corinthians
13:13-14, Philippians 1:16-17) are documented versification differences
where the KJV numbers verses differently than the reference system TAGNT
uses — the text isn't missing, just numbered differently upstream.

One real bug worth knowing about, in case you extend this further: the
source files sometimes give a reference like `Psa.3.1(3.2)#01`, where the
primary number matches English/KJV-style versification and the
parenthetical is the Hebrew Bible's own numbering (Hebrew often counts a
psalm's superscription as verse 1, shifting everything after it by one).
The parser matches on the *primary* (pre-parenthesis) reference — missing
that parenthesis entirely on the first pass silently dropped ~21,000 valid
tags (mostly Psalms with superscriptions) before it was caught by
comparing OT coverage against NT coverage and noticing OT was
suspiciously lower.

Each verse's `word_tags` array in `/api/passage/` contains: `position`,
`original_word`, `transliteration`, `gloss`, `strongs_number`,
`morphology` — in original-language word order. Note this is Greek/Hebrew
word order, not KJV English word order, since the whole point is that the
two don't map one-to-one; use `position` to preserve original sequence
rather than trying to align it to the English text index-for-index. Hebrew
prefixed clitics (the/and/in) are bundled into the same tag as the word
they attach to (e.g. "in/beginning" is one `WordTag`, matching how the
source data groups them), tagged with the root word's Strong's number.

## Full-Bible cross-references (votes-ranked)

`load_cross_references` loads
[OpenBible.info's cross-reference dataset](https://www.openbible.info/labs/cross-references/)
(CC BY 4.0, ~344,800 rows, primarily sourced from the public-domain
*Treasury of Scripture Knowledge*, with a crowd-sourced relevance score
called "votes"). Bundled at `bible/fixtures/crossrefs/cross_references.txt`.

This is distinct from the existing `CrossReference` model (a handful of
hand-curated, thematically-tagged references used by `seed_sample_data`
for the 4 demo passages). The new `CrossReferenceLink` model holds the
full public dataset instead: no theme tag, but a real relevance ranking
and full-Bible coverage. Both appear in `/api/passage/` — `cross_references`
(curated) and `bulk_cross_references` (the full dataset, top 10 by votes
per verse by default; override with `?xref_limit=N`).

**Verified results:** 344,798 of 344,800 rows loaded (one is the header
row; the single genuine exception is a reference to 3 John 1:15, which
doesn't exist in the KJV's 14-verse numbering of that book — some
Greek-text-based versifications split KJV's combined final verse into two,
a well-documented and harmless edge case, not a data error). 29,363 of
31,102 KJV verses (94.4%) have at least one cross-reference, matching
OpenBible.info's own published coverage figures.

The "to" side of a reference can be a verse range, and — in 18 rare cases
out of 344,800 — that range crosses a book boundary entirely (e.g.
2 Chronicles 36:22-23 pointing to Ezra 1:1-3, since Ezra opens by quoting
the decree that closes Chronicles). This is handled correctly: I
specifically tested this exact case against the live API and confirmed
both the in-book and cross-book ranges format their `reference_label`
correctly (e.g. `"Ezra 1:1-3"`).

Votes can be negative (0.34% of rows) when a suggested cross-reference was
crowd-downvoted as not actually relevant; these are kept in the data
(ordering by votes naturally pushes them to the bottom) rather than
silently dropped, so nothing is hidden from an API consumer who wants to
inspect or filter them.

## Adding more translations

The full KJV is already loaded. To add NIV, ESV, etc., you'll need each
one as a JSON file in the same nested shape, then run:

```bash
python manage.py load_bible_json --file /path/to/other_version.json --translation NIV
```

Note: NIV/ESV/NASB are copyrighted, so make sure you have the right to
store and serve that text before loading and shipping it — this differs
from the KJV, which is public domain.

[//]: # (## Production notes)

[//]: # ()
[//]: # (This ships with Django's development server and SQLite for simplicity.)

[//]: # (Before deploying:)

[//]: # (- Switch `DEBUG = False` and set `ALLOWED_HOSTS` in `config/settings.py`.)

[//]: # (- Move `SECRET_KEY` to an environment variable.)

[//]: # (- Swap SQLite for Postgres for anything beyond light personal use.)

[//]: # (- Serve via Gunicorn/Uvicorn behind Nginx &#40;or a PaaS like Railway/Render&#41;.)

[//]: # (- Restrict `CORS_ALLOWED_ORIGINS` to your actual frontend's domain.)
