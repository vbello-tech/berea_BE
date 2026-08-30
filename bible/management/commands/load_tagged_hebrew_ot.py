import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bible.models import Book, Verse, StrongsEntry, WordTag
from bible.step_book_map import STEP_BOOK_MAP
from bible.tagged_text_common import REF_RE, normalize_strongs

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / 'fixtures' / 'tahot'


class Command(BaseCommand):
    help = (
        "Load real word-by-word Strong's tagging from STEPBible-Data TAHOT "
        "files (Translators Amalgamated Hebrew OT), matching each tagged "
        "word to an already-loaded Verse by book/chapter/verse. Run "
        "load_bible_json and load_strongs first."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', type=str, action='append', dest='files',
            help='Path to a TAHOT .txt file. Repeatable. Defaults to all '
                 'four bundled OT files if omitted.',
        )
        parser.add_argument(
            '--translation', type=str, default='KJV',
            help='Which loaded translation to attach tags to (default: KJV).',
        )

    def handle(self, *args, **options):
        files = options['files'] or [
            FIXTURES_DIR / 'TAHOT_Gen-Deu.txt',
            FIXTURES_DIR / 'TAHOT_Jos-Est.txt',
            FIXTURES_DIR / 'TAHOT_Job-Sng.txt',
            FIXTURES_DIR / 'TAHOT_Isa-Mal.txt',
        ]
        translation = options['translation'].upper()

        verse_lookup = {
            (b_id, ch, vn): v_id
            for v_id, b_id, ch, vn in Verse.objects.filter(translation=translation)
            .values_list('id', 'book_id', 'chapter', 'verse_number')
        }
        book_id_by_name = dict(Book.objects.values_list('name', 'id'))
        strongs_id_by_number = dict(StrongsEntry.objects.values_list('number', 'id'))

        if not verse_lookup:
            raise CommandError(
                f"No verses found for translation={translation}. Run "
                "load_bible_json first."
            )

        total_created = 0
        for file_path in files:
            file_path = Path(file_path)
            if not file_path.exists():
                self.stdout.write(self.style.WARNING(f'Skipping missing file: {file_path}'))
                continue
            created = self._load_file(
                file_path, translation, verse_lookup, book_id_by_name, strongs_id_by_number
            )
            total_created += created
            self.stdout.write(self.style.SUCCESS(f'{file_path.name}: created {created} word tags'))

        self.stdout.write(self.style.SUCCESS(f'Done. Total word tags created: {total_created}'))

    def _load_file(self, file_path, translation, verse_lookup, book_id_by_name, strongs_id_by_number):
        unknown_books = set()
        unmatched_verses = set()
        to_create = []

        with open(file_path, encoding='utf-8-sig') as f:
            for line in f:
                m = REF_RE.match(line)
                if not m:
                    continue  # header/metadata/summary rows

                abbrev, chapter, verse_num, word_index = m.groups()
                fields = line.rstrip('\n').split('\t')
                if len(fields) < 9:
                    continue

                book_name = STEP_BOOK_MAP.get(abbrev)
                if not book_name:
                    unknown_books.add(abbrev)
                    continue
                book_id = book_id_by_name.get(book_name)
                if book_id is None:
                    continue

                verse_id = verse_lookup.get((book_id, int(chapter), int(verse_num)))
                if verse_id is None:
                    unmatched_verses.add(f"{book_name} {chapter}:{verse_num}")
                    continue

                # TAHOT columns: Ref, Hebrew, Transliteration, Translation,
                # dStrongs, Grammar, Meaning Variants, Spelling Variants,
                # Root dStrong+Instance, Alternative Strongs+Instance,
                # Conjoin word, Expanded Strong tags.
                #
                # Hebrew prefixed clitics (the/and/in) are bundled into the
                # same cell as the root word, separated by "/" -- e.g.
                # "בְּ/רֵאשִׁ֖ית" ("in"+"beginning"). We keep the whole cell
                # as one WordTag (matching STEPBible's own word grouping)
                # and tag it with the ROOT word's Strong's number from
                # column 8, which already excludes the prefix's pseudo
                # Strong's number (STEP's internal H9001-H9016 range for
                # articles/conjunctions/prepositions, not real lexicon
                # entries).
                original_word = fields[1].strip()
                transliteration = fields[2].strip() if len(fields) > 2 else ''
                gloss = fields[3].strip() if len(fields) > 3 else ''
                morph = fields[5].strip() if len(fields) > 5 else ''

                root_strong_raw = fields[8].strip() if len(fields) > 8 else ''
                strongs_number = normalize_strongs(root_strong_raw)
                if not strongs_number:
                    # Fall back to the first real (non-prefix) number in
                    # the combined dStrongs column if the root column is
                    # empty for some reason.
                    for token in re.split(r'[/\\]', fields[4]) if len(fields) > 4 else []:
                        strongs_number = normalize_strongs(token)
                        if strongs_number:
                            break
                if not strongs_number:
                    continue

                to_create.append(WordTag(
                    verse_id=verse_id,
                    position=int(word_index),
                    original_word=original_word,
                    transliteration=transliteration,
                    gloss=gloss,
                    strongs_number=strongs_number,
                    morphology=morph,
                    strongs_entry_id=strongs_id_by_number.get(strongs_number),
                ))

        if unknown_books:
            self.stdout.write(self.style.WARNING(f'Unknown book abbreviations skipped: {sorted(unknown_books)}'))
        if unmatched_verses:
            self.stdout.write(self.style.WARNING(
                f'{len(unmatched_verses)} verse reference(s) had no matching KJV verse '
                f'(likely versification differences) -- e.g. {list(unmatched_verses)[:5]}'
            ))

        with transaction.atomic():
            WordTag.objects.bulk_create(to_create, batch_size=2000)

        return len(to_create)
