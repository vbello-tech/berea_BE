import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from bible.models import Book, Verse, StrongsEntry, WordTag
from bible.tagged_text_common import normalize_strongs

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / 'fixtures' / 'tahot'

# Matches only the superscription rows: primary verse number is literally 0,
# e.g. "Psa.3.0(3.1)#01=L". These are Psalm headings ("A Psalm of David...")
# that Hebrew/Masoretic numbering counts as verse 0 (or folds into verse 1
# of its own scheme) but which the KJV doesn't assign a verse number to at
# all -- so load_tagged_hebrew_ot correctly finds no matching KJV verse and
# skips them. This command creates that missing verse instead of skipping.
SUPERSCRIPTION_REF_RE = re.compile(r'^Psa\.(\d+)\.0(?:\([^)]*\))?#(\d+)=')


class Command(BaseCommand):
    help = (
        "Add the ~116 Psalm superscription verses (Hebrew verse 0) that "
        "load_tagged_hebrew_ot reports as unmatched, since the KJV doesn't "
        "number them. Creates each as verse_number=0 on the relevant Psalm, "
        "with text reconstructed from the TAHOT word-level English gloss "
        "(not authentic 1611 KJV wording -- see README note), plus real "
        "WordTag rows for each Hebrew word, same as the main loader."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', type=str, action='append', dest='files',
            help='Path to a TAHOT .txt file. Repeatable. Defaults to all '
                 'four bundled OT files if omitted.',
        )
        parser.add_argument(
            '--translation', type=str, default='KJV',
            help='Which translation to attach these verses to (default: KJV).',
        )

    def handle(self, *args, **options):
        files = options['files'] or [
            FIXTURES_DIR / 'TAHOT_Gen-Deu.txt',
            FIXTURES_DIR / 'TAHOT_Jos-Est.txt',
            FIXTURES_DIR / 'TAHOT_Job-Sng.txt',
            FIXTURES_DIR / 'TAHOT_Isa-Mal.txt',
        ]
        translation = options['translation'].upper()

        try:
            psalm = Book.objects.get(name='Psalm')
        except Book.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                "No 'Psalm' book found -- run load_bible_json first."
            ))
            return

        strongs_id_by_number = dict(StrongsEntry.objects.values_list('number', 'id'))

        # Gather all superscription word-rows, grouped by chapter, across
        # whichever files contain them (in practice just Job-Sng, since
        # that's where Psalms lives, but scanning all four is harmless).
        by_chapter = {}
        for file_path in files:
            file_path = Path(file_path)
            if not file_path.exists():
                continue
            with open(file_path, encoding='utf-8-sig') as f:
                for line in f:
                    m = SUPERSCRIPTION_REF_RE.match(line)
                    if not m:
                        continue
                    chapter, word_index = m.groups()
                    fields = line.rstrip('\n').split('\t')
                    if len(fields) < 9:
                        continue
                    by_chapter.setdefault(int(chapter), []).append({
                        'position': int(word_index),
                        'original_word': fields[1].strip(),
                        'transliteration': fields[2].strip() if len(fields) > 2 else '',
                        'gloss': fields[3].strip() if len(fields) > 3 else '',
                        'morphology': fields[5].strip() if len(fields) > 5 else '',
                        'strongs_raw': fields[8].strip() if len(fields) > 8 else '',
                    })

        created_verses = 0
        created_tags = 0
        skipped_existing = 0

        with transaction.atomic():
            for chapter, words in sorted(by_chapter.items()):
                words.sort(key=lambda w: w['position'])

                verse, was_created = Verse.objects.get_or_create(
                    book=psalm, chapter=chapter, verse_number=0, translation=translation,
                    defaults={'text': self._reconstruct_text(words)},
                )
                if not was_created:
                    skipped_existing += 1
                    continue
                created_verses += 1

                for w in words:
                    strongs_number = normalize_strongs(w['strongs_raw'])
                    if not strongs_number:
                        continue
                    WordTag.objects.create(
                        verse=verse,
                        position=w['position'],
                        original_word=w['original_word'],
                        transliteration=w['transliteration'],
                        gloss=w['gloss'],
                        strongs_number=strongs_number,
                        morphology=w['morphology'],
                        strongs_entry_id=strongs_id_by_number.get(strongs_number),
                    )
                    created_tags += 1

        self.stdout.write(self.style.SUCCESS(
            f'Created {created_verses} superscription verse(s) with {created_tags} word tag(s). '
            f'Skipped {skipped_existing} that already existed.'
        ))
        if created_verses:
            self.stdout.write(self.style.WARNING(
                'Note: this text is reconstructed from the TAHOT interlinear gloss, '
                'not authentic 1611 KJV wording -- see README for details. '
                'Edit these verses in /admin/ if you want to replace them with '
                'the traditional KJV heading text by hand.'
            ))

    @staticmethod
    def _reconstruct_text(words):
        parts = []
        for w in words:
            gloss = w['gloss'].replace('/', ' ')
            gloss = re.sub(r'\s+', ' ', gloss).strip()
            if gloss:
                parts.append(gloss)
        text = ' '.join(parts)
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            return '(heading)'
        text = text[0].upper() + text[1:]
        if not text.endswith(('.', '!', '?')):
            text += '.'
        return text
