"""
Management command: load_kjv_strongs_tags_from_sword

Populates KjvStrongsTag from a KJV+Strong's JSON extracted from the
CrossWire/SWORD "KJVA" zText module -- replacing the earlier, lower-quality
load_kjv_strongs_tags (sourced from kaiserlik/kjv), which was never
actually wired into the interlinear tab. This source's Strong's numbers
follow the same root/canonical numbering convention as STEPBible's own
TAHOT/TAGNT (used for word_tags), and its structure is much cleaner: each
entry is a real English phrase-chunk aligned to one or more original-
language words, rather than a naive whitespace token split.

Expected JSON shape (see load_kjv_render_text_from_sword.py for the same
shape description):
{
  "books": [
    {"name": "Genesis", "testament": "OT", "chapters": [
      {"chapter": 1, "verses": [
        {"verse": 1, "words": [
          {"text": "In the beginning", "strongs": ["H07225"]},
          {"text": "created", "strongs": ["H0853", "H01254"], "morph": [...]},
          ...
        ]}
      ]}
    ]}
  ]
}

`position` is assigned as the word entry's index within the verse's
`words` array (1-based) -- this is real KJV English word order, matching
KjvStrongsTag.position's documented meaning exactly. When a single phrase
carries more than one Strong's number (e.g. an untranslated object marker
folded into a verb), multiple rows are created sharing that same position
and surface_word -- the shape KjvStrongsTag's own docstring already
documents as expected.

Usage:
    python manage.py load_kjv_strongs_tags_from_sword --file kjv_strongs.json --dry-run
    python manage.py load_kjv_strongs_tags_from_sword --file kjv_strongs.json --clear
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bible.book_order import BOOK_NAME_BY_LOWER
from bible.models import StrongsEntry, Verse, KjvStrongsTag
from bible.tagged_text_common import normalize_strongs

# This source spells out ordinal book-name prefixes as words ("I", "II",
# "III") rather than digits, and uses a couple of alternate full names
# ("Psalms" plural, "Revelation of John") that don't match this project's
# canonical BOOK_NAME_BY_LOWER keys. Checked first, before falling back
# to BOOK_NAME_BY_LOWER for every other (already-matching) book name.
SOURCE_BOOK_NAME_OVERRIDES = {
    'i chronicles': '1 Chronicles', 'ii chronicles': '2 Chronicles',
    'i corinthians': '1 Corinthians', 'ii corinthians': '2 Corinthians',
    'i john': '1 John', 'ii john': '2 John', 'iii john': '3 John',
    'i kings': '1 Kings', 'ii kings': '2 Kings',
    'i peter': '1 Peter', 'ii peter': '2 Peter',
    'i samuel': '1 Samuel', 'ii samuel': '2 Samuel',
    'i thessalonians': '1 Thessalonians', 'ii thessalonians': '2 Thessalonians',
    'i timothy': '1 Timothy', 'ii timothy': '2 Timothy',
    'psalms': 'Psalm',
    'revelation of john': 'Revelation',
}


def resolve_sword_book_name(raw_name):
    key = (raw_name or '').strip().lower()
    if key in SOURCE_BOOK_NAME_OVERRIDES:
        override = SOURCE_BOOK_NAME_OVERRIDES[key]
        # Confirm the override target actually exists as a canonical name
        # (guards against a typo in the override table itself rather than
        # silently resolving to a book that isn't really in the DB).
        return override if override.lower() in BOOK_NAME_BY_LOWER else None
    return BOOK_NAME_BY_LOWER.get(key)


class Command(BaseCommand):
    help = (
        "Load KjvStrongsTag from a SWORD-derived KJV+Strong's JSON. "
        "Replaces the earlier kaiserlik/kjv-sourced data with this "
        "higher-quality, canonically-numbered source."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', type=str, action='append', dest='files', required=True,
            help='Path to the JSON file(s). Repeatable (e.g. separate OT/NT files).',
        )
        parser.add_argument(
            '--translation', type=str, default='KJV',
            help='Which loaded translation to attach these tags to (default: KJV).',
        )
        parser.add_argument(
            '--clear', action='store_true',
            help="Delete all existing KjvStrongsTag rows for this translation before "
                 "loading. Recommended -- without it, re-running this command (or "
                 "having previously run load_kjv_strongs_tags) will duplicate rows, "
                 "since neither loader checks for existing data first.",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report what would happen without writing anything.",
        )

    def handle(self, *args, **options):
        translation = options['translation'].upper()
        dry_run = options['dry_run']

        verse_lookup = {
            (b_id, ch, vn): v_id
            for v_id, b_id, ch, vn in Verse.objects.filter(translation=translation)
            .values_list('id', 'book_id', 'chapter', 'verse_number')
        }
        book_id_by_name = {}
        for book_id, book_name in Verse.objects.filter(translation=translation).values_list('book_id', 'book__name').distinct():
            book_id_by_name[book_name] = book_id
        strongs_id_by_number = dict(StrongsEntry.objects.values_list('number', 'id'))

        if not verse_lookup:
            raise CommandError(f"No verses found for translation={translation}. Run load_bible_json first.")

        totals = {'unresolved_books': set(), 'unmatched_verses': 0, 'verses_seen': 0, 'rows_created': 0}
        to_create = []

        with transaction.atomic():
            if options['clear']:
                deleted, _ = KjvStrongsTag.objects.filter(verse__translation=translation).delete()
                self.stdout.write(self.style.WARNING(f"Cleared {deleted} existing KjvStrongsTag row(s) for {translation}."))

            for file_path in options['files']:
                path = Path(file_path)
                if not path.exists():
                    raise CommandError(f"File not found: {path}")
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)

                for book in data.get('books', []):
                    canonical_book = resolve_sword_book_name(book.get('name'))
                    if not canonical_book:
                        totals['unresolved_books'].add(book.get('name', '<unnamed>'))
                        continue
                    book_id = book_id_by_name.get(canonical_book)
                    if book_id is None:
                        totals['unresolved_books'].add(book.get('name', '<unnamed>'))
                        continue

                    for chapter_entry in book.get('chapters', []):
                        chapter = chapter_entry.get('chapter')

                        for verse_entry in chapter_entry.get('verses', []):
                            verse_number = verse_entry.get('verse')
                            totals['verses_seen'] += 1

                            verse_id = verse_lookup.get((book_id, chapter, verse_number))
                            if verse_id is None:
                                totals['unmatched_verses'] += 1
                                continue

                            for idx, w in enumerate(verse_entry.get('words', [])):
                                position = idx + 1
                                surface_word = (w.get('text') or '').strip()
                                strongs_list = w.get('strongs') or []
                                morph_list = w.get('morph') or []
                                for i, raw_strongs in enumerate(strongs_list):
                                    norm = normalize_strongs((raw_strongs or '').upper())
                                    if not norm:
                                        continue
                                    # Pair by index: when the source has one morph
                                    # code per strongs number (the common case),
                                    # each row gets its own correct code. When
                                    # there are fewer morph entries than strongs
                                    # (e.g. an untranslated object marker folded
                                    # into a verb, with only the verb's morph
                                    # given), extra strongs entries beyond the
                                    # morph list simply get blank rather than a
                                    # guessed/duplicated value.
                                    morphology = morph_list[i].strip() if i < len(morph_list) and morph_list[i] else ''
                                    to_create.append(KjvStrongsTag(
                                        verse_id=verse_id,
                                        position=position,
                                        surface_word=surface_word,
                                        strongs_number=norm,
                                        morphology=morphology,
                                        strongs_entry_id=strongs_id_by_number.get(norm),
                                    ))

            if not dry_run:
                KjvStrongsTag.objects.bulk_create(to_create, batch_size=2000)
            totals['rows_created'] = len(to_create)

            if dry_run:
                transaction.set_rollback(True)

        if totals['unresolved_books']:
            self.stdout.write(self.style.WARNING(f"Unresolved book names: {sorted(totals['unresolved_books'])}"))

        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY RUN] ' if dry_run else ''}"
            f"Verses seen: {totals['verses_seen']}, no matching {translation} verse: {totals['unmatched_verses']}\n"
            f"KjvStrongsTag rows created: {totals['rows_created']}"
        ))

