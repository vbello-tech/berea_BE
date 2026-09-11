"""
Management command: load_kjv_strongs_richtags

Loads a KJV-specific dataset laid out in the same column format as
STEPBible's TAHOT (OT) / TAGNT (NT) files, but tagged to actual KJV
wording rather than the official STEPBible originals. Populates
KjvStrongsTag with original_word (Hebrew/Greek script, when given),
transliteration, surface_word (the "Translation" column -- literal KJV
wording for that instance), strongs_number, and morphology -- giving KJV
rows the same five-field shape as word_tags (BSB's source), so both can
render identically in the interlinear tab.

NOTE: this source's word ordering follows KJV ENGLISH surface order (verified
against Gen 1:1: "In the beginning", "God", "created" -- subject before verb,
which is English SVO, not Hebrew's VSO), same as the earlier SWORD-derived
data. Position is taken directly from the source's own "#NN" instance
counter per verse, which already reflects this order -- no realignment
needed since we're not trying to match word_tags' position numbering here.

Expects a single file containing both OT and NT sections, each preceded
by a line containing "OLD TESTAMENT" / "NEW TESTAMENT" (as pasted), OR
separate --ot-file / --nt-file. Column layouts differ between sections:

OT columns (tab-separated): Ref, Hebrew, Translit, Translation, dStrongs,
Grammar, MeaningVariants, SpellingVariants, RootDStrong+Instance,
AltStrongs+Instance, ConjoinWord, ExpandedStrongTags

NT columns (tab-separated): Ref, Greek, Translation, "dStrongs=Grammar",
"DictForm=Gloss", editions, MeaningVariants, SpellingVariants,
SpanishTranslation, SubMeaning, ConjoinWord, sStrong+Instance, AltStrongs

dStrongs can carry more than one number separated by "/" (e.g.
"H0853/H01254" -- an untranslated object marker folded into a verb's
rendering). One KjvStrongsTag row is created per number, sharing the same
position/surface_word/original_word/transliteration -- the same
multi-strongs-per-position shape already used elsewhere in this project.

Usage:
    python manage.py load_kjv_strongs_richtags --file combined.txt --clear --dry-run
    python manage.py load_kjv_strongs_richtags --ot-file ot.txt --nt-file nt.txt --clear
"""
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bible.models import StrongsEntry, Verse, KjvStrongsTag
from bible.step_book_map import STEP_BOOK_MAP
from bible.tagged_text_common import normalize_strongs

# Matches "Gen.1.1#01" / "Mat.1.1#01" style refs at the start of a line.
REF_RE = re.compile(r'^([A-Za-z0-9]+)\.(\d+)\.(\d+)#(\d+)')


class Command(BaseCommand):
    help = "Load a KJV-specific TAHOT/TAGNT-style dataset into rich KjvStrongsTag rows."

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, default=None, help='Single file containing both OT and NT sections.')
        parser.add_argument('--ot-file', type=str, default=None, help='OT-only file.')
        parser.add_argument('--nt-file', type=str, default=None, help='NT-only file.')
        parser.add_argument('--translation', type=str, default='KJV')
        parser.add_argument('--clear', action='store_true', help='Delete existing KjvStrongsTag rows first.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        translation = options['translation'].upper()
        dry_run = options['dry_run']

        if not options['file'] and not (options['ot_file'] or options['nt_file']):
            raise CommandError("Provide --file, or --ot-file/--nt-file.")

        verse_lookup = {
            (b_id, ch, vn): v_id
            for v_id, b_id, ch, vn in Verse.objects.filter(translation=translation)
            .values_list('id', 'book_id', 'chapter', 'verse_number')
        }
        if not verse_lookup:
            raise CommandError(f"No verses found for translation={translation}. Run load_bible_json first.")

        from bible.models import Book
        book_id_by_name = dict(Book.objects.values_list('name', 'id'))
        strongs_id_by_number = dict(StrongsEntry.objects.values_list('number', 'id'))

        totals = {'ot_rows': 0, 'nt_rows': 0, 'unknown_books': set(), 'unmatched_verses': set(), 'created': 0}
        to_create = []

        with transaction.atomic():
            if options['clear']:
                deleted, _ = KjvStrongsTag.objects.filter(verse__translation=translation).delete()
                self.stdout.write(self.style.WARNING(f"Cleared {deleted} existing KjvStrongsTag row(s)."))

            if options['file']:
                self._parse_combined_file(
                    options['file'], verse_lookup, book_id_by_name, strongs_id_by_number, totals, to_create,
                )
            else:
                if options['ot_file']:
                    self._parse_section(
                        options['ot_file'], 'ot', verse_lookup, book_id_by_name, strongs_id_by_number, totals, to_create,
                    )
                if options['nt_file']:
                    self._parse_section(
                        options['nt_file'], 'nt', verse_lookup, book_id_by_name, strongs_id_by_number, totals, to_create,
                    )

            if not dry_run:
                KjvStrongsTag.objects.bulk_create(to_create, batch_size=2000)
            totals['created'] = len(to_create)

            if dry_run:
                transaction.set_rollback(True)

        if totals['unknown_books']:
            self.stdout.write(self.style.WARNING(f"Unknown book abbreviations skipped: {sorted(totals['unknown_books'])}"))
        if totals['unmatched_verses']:
            self.stdout.write(self.style.WARNING(
                f"{len(totals['unmatched_verses'])} verse ref(s) had no matching {translation} verse "
                f"(e.g. {list(totals['unmatched_verses'])[:5]})"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY RUN] ' if dry_run else ''}"
            f"OT rows parsed: {totals['ot_rows']}, NT rows parsed: {totals['nt_rows']}, "
            f"KjvStrongsTag rows created: {totals['created']}"
        ))

    def _parse_combined_file(self, path, verse_lookup, book_id_by_name, strongs_id_by_number, totals, to_create):
        mode = None
        with open(path, encoding='utf-8-sig') as f:
            for line in f:
                if 'OLD TESTAMENT' in line:
                    mode = 'ot'
                    continue
                if 'NEW TESTAMENT' in line:
                    mode = 'nt'
                    continue
                if mode is None:
                    continue
                self._parse_line(line, mode, verse_lookup, book_id_by_name, strongs_id_by_number, totals, to_create)

    def _parse_section(self, path, mode, verse_lookup, book_id_by_name, strongs_id_by_number, totals, to_create):
        with open(path, encoding='utf-8-sig') as f:
            for line in f:
                self._parse_line(line, mode, verse_lookup, book_id_by_name, strongs_id_by_number, totals, to_create)

    def _parse_line(self, line, mode, verse_lookup, book_id_by_name, strongs_id_by_number, totals, to_create):
        m = REF_RE.match(line)
        if not m:
            return  # header/blank/section-title row

        abbrev, chapter, verse_num, word_index = m.groups()
        fields = line.rstrip('\n').split('\t')

        book_name = STEP_BOOK_MAP.get(abbrev)
        if not book_name:
            totals['unknown_books'].add(abbrev)
            return
        book_id = book_id_by_name.get(book_name)
        if book_id is None:
            totals['unknown_books'].add(abbrev)
            return

        verse_id = verse_lookup.get((book_id, int(chapter), int(verse_num)))
        if verse_id is None:
            totals['unmatched_verses'].add(f"{book_name} {chapter}:{verse_num}")
            return

        if mode == 'ot':
            totals['ot_rows'] += 1
            # Ref, Hebrew, Translit, Translation, dStrongs, Grammar, ...
            original_word = fields[1].strip() if len(fields) > 1 else ''
            transliteration = fields[2].strip() if len(fields) > 2 else ''
            surface_word = fields[3].strip() if len(fields) > 3 else ''
            raw_dstrongs = fields[4].strip() if len(fields) > 4 else ''
            morphology = fields[5].strip() if len(fields) > 5 else ''
        else:
            totals['nt_rows'] += 1
            # Ref, Greek, Translation, "dStrongs=Grammar", "DictForm=Gloss", ...
            original_word = fields[1].strip() if len(fields) > 1 else ''
            surface_word = fields[2].strip() if len(fields) > 2 else ''
            transliteration = ''  # not provided in the NT layout
            dstrongs_grammar = fields[3].strip() if len(fields) > 3 else ''
            raw_dstrongs, _, morphology = dstrongs_grammar.partition('=')

        for raw_strongs in raw_dstrongs.split('/'):
            norm = normalize_strongs(raw_strongs.strip().upper())
            if not norm:
                continue
            to_create.append(KjvStrongsTag(
                verse_id=verse_id,
                position=int(word_index),
                surface_word=surface_word,
                original_word=original_word,
                transliteration=transliteration,
                strongs_number=norm,
                morphology=morphology,
                strongs_entry_id=strongs_id_by_number.get(norm),
            ))
