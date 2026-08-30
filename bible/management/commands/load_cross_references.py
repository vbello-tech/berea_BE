import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bible.models import Book, Verse, CrossReferenceLink
from bible.crossref_book_map import CROSSREF_BOOK_MAP

DEFAULT_FILE = Path(__file__).resolve().parent.parent.parent / 'fixtures' / 'crossrefs' / 'cross_references.txt'

# A single reference, e.g. "Gen.1.1" or "1Chr.16.26"
SINGLE_REF_RE = re.compile(r'^([A-Za-z0-9]+)\.(\d+)\.(\d+)$')

# The "to" side, which may be a range: "Gen.1.1" or "Gen.1.1-Gen.1.3"
# (ranges can cross chapters, and rarely books, so both sides are parsed
# independently rather than assumed to share a book/chapter).
RANGE_RE = re.compile(
    r'^([A-Za-z0-9]+)\.(\d+)\.(\d+)(?:-([A-Za-z0-9]+)\.(\d+)\.(\d+))?$'
)


class Command(BaseCommand):
    help = (
        "Load OpenBible.info's cross-reference dataset (CC BY 4.0), matching "
        "the 'from' side to an already-loaded Verse by book/chapter/verse. "
        "Run load_bible_json first."
    )

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, default=str(DEFAULT_FILE))
        parser.add_argument(
            '--translation', type=str, default='KJV',
            help='Which loaded translation to attach cross-references to (default: KJV).',
        )

    def handle(self, *args, **options):
        file_path = Path(options['file'])
        translation = options['translation'].upper()

        if not file_path.exists():
            raise CommandError(f'File not found: {file_path}')

        verse_lookup = {
            (b_id, ch, vn): v_id
            for v_id, b_id, ch, vn in Verse.objects.filter(translation=translation)
            .values_list('id', 'book_id', 'chapter', 'verse_number')
        }
        book_id_by_name = dict(Book.objects.values_list('name', 'id'))

        if not verse_lookup:
            raise CommandError(
                f"No verses found for translation={translation}. Run load_bible_json first."
            )

        unknown_books = set()
        unmatched_from = 0
        skipped_bad_row = 0
        to_create = []

        with open(file_path, encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if not line or line.startswith('From Verse'):
                    continue  # header row

                parts = line.split('\t')
                if len(parts) < 3:
                    skipped_bad_row += 1
                    continue

                from_raw, to_raw, votes_raw = parts[0], parts[1], parts[2]

                from_m = SINGLE_REF_RE.match(from_raw)
                if not from_m:
                    skipped_bad_row += 1
                    continue
                from_abbrev, from_ch, from_vs = from_m.groups()
                from_book_name = CROSSREF_BOOK_MAP.get(from_abbrev)
                if not from_book_name:
                    unknown_books.add(from_abbrev)
                    continue
                from_book_id = book_id_by_name.get(from_book_name)
                if from_book_id is None:
                    continue
                from_verse_id = verse_lookup.get((from_book_id, int(from_ch), int(from_vs)))
                if from_verse_id is None:
                    unmatched_from += 1
                    continue

                to_m = RANGE_RE.match(to_raw)
                if not to_m:
                    skipped_bad_row += 1
                    continue
                (s_abbrev, s_ch, s_vs, e_abbrev, e_ch, e_vs) = to_m.groups()
                s_book_name = CROSSREF_BOOK_MAP.get(s_abbrev)
                if not s_book_name:
                    unknown_books.add(s_abbrev)
                    continue
                if e_abbrev:
                    e_book_name = CROSSREF_BOOK_MAP.get(e_abbrev)
                    if not e_book_name:
                        unknown_books.add(e_abbrev)
                        continue
                else:
                    e_book_name, e_ch, e_vs = s_book_name, s_ch, s_vs

                try:
                    votes = int(votes_raw)
                except ValueError:
                    skipped_bad_row += 1
                    continue

                to_create.append(CrossReferenceLink(
                    from_verse_id=from_verse_id,
                    to_book_start=s_book_name, to_chapter_start=int(s_ch), to_verse_start=int(s_vs),
                    to_book_end=e_book_name, to_chapter_end=int(e_ch), to_verse_end=int(e_vs),
                    votes=votes,
                ))

        with transaction.atomic():
            CrossReferenceLink.objects.bulk_create(to_create, batch_size=5000)

        if unknown_books:
            self.stdout.write(self.style.WARNING(f'Unknown book abbreviations skipped: {sorted(unknown_books)}'))
        if unmatched_from:
            self.stdout.write(self.style.WARNING(
                f'{unmatched_from} "from" reference(s) had no matching {translation} verse.'
            ))
        if skipped_bad_row:
            self.stdout.write(self.style.WARNING(f'{skipped_bad_row} malformed row(s) skipped.'))

        self.stdout.write(self.style.SUCCESS(f'Loaded {len(to_create)} cross-reference links.'))
