import json
from pathlib import Path

from django.core.management.base import BaseCommand
from bible.models import StrongsEntry

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / 'fixtures' / 'strongs'


class Command(BaseCommand):
    help = (
        "Load the Strong's Greek + Hebrew lexicon (definitions only) from "
        "bible/fixtures/strongs/*.json, converted from "
        "https://github.com/openscriptures/strongs"
    )

    def handle(self, *args, **options):
        self._load('strongs_greek.json', 'greek')
        self._load('strongs_hebrew.json', 'hebrew')

    def _load(self, filename, language):
        path = FIXTURES_DIR / filename
        if not path.exists():
            self.stdout.write(self.style.ERROR(f'Missing fixture: {path}'))
            return

        with open(path, encoding='utf-8') as f:
            data = json.load(f)

        entries = []
        for number, fields in data.items():
            entries.append(StrongsEntry(
                number=number,
                language=language,
                lemma=fields.get('lemma', '') or '',
                translit=fields.get('translit', fields.get('xlit', '')) or '',
                pronunciation=fields.get('pron', '') or '',
                derivation=fields.get('derivation', '') or '',
                strongs_def=fields.get('strongs_def', '') or '',
                kjv_def=fields.get('kjv_def', '') or '',
            ))

        # Bulk load, skipping any numbers already present.
        existing = set(StrongsEntry.objects.filter(language=language).values_list('number', flat=True))
        new_entries = [e for e in entries if e.number not in existing]
        StrongsEntry.objects.bulk_create(new_entries, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f'Loaded {len(new_entries)} new {language} entries ({len(entries)} total in source file).'
        ))
