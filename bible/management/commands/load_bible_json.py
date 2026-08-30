import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bible.models import Book, Verse
from bible.book_order import BOOK_ORDER_MAP

DEFAULT_FILE = Path(__file__).resolve().parent.parent.parent / 'fixtures' / 'kjv' / 'KJV_bible.json'


class Command(BaseCommand):
    help = (
        "Load a full Bible translation from a JSON file shaped as "
        '{ "BookName": { "chapter": { "verse": "text" } } }. '
        "Defaults to the bundled KJV file."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', type=str, default=str(DEFAULT_FILE),
            help='Path to the JSON file (default: bundled KJV file).',
        )
        parser.add_argument(
            '--translation', type=str, default='KJV',
            help='Translation code to store on each verse, e.g. KJV, NIV, ESV (default: KJV).',
        )

    def handle(self, *args, **options):
        file_path = Path(options['file'])
        translation = options['translation'].upper()

        if not file_path.exists():
            raise CommandError(f'File not found: {file_path}')

        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)

        unknown_books = [name for name in data if name not in BOOK_ORDER_MAP]
        if unknown_books:
            self.stdout.write(self.style.WARNING(
                f"Skipping {len(unknown_books)} book(s) not in the canonical book list "
                f"(check spelling against bible/book_order.py): {unknown_books}"
            ))

        # Ensure all Book rows exist first.
        books_by_name = {}
        for name, (order, testament) in BOOK_ORDER_MAP.items():
            if name in data:
                book, _ = Book.objects.get_or_create(
                    name=name, defaults={'order': order, 'testament': testament}
                )
                books_by_name[name] = book

        existing_keys = set(
            Verse.objects.filter(translation=translation).values_list(
                'book_id', 'chapter', 'verse_number'
            )
        )

        to_create = []
        total_in_file = 0
        for book_name, chapters in data.items():
            book = books_by_name.get(book_name)
            if book is None:
                continue
            for chapter_str, verses in chapters.items():
                chapter = int(chapter_str)
                for verse_str, text in verses.items():
                    total_in_file += 1
                    verse_num = int(verse_str)
                    key = (book.id, chapter, verse_num)
                    if key in existing_keys:
                        continue
                    to_create.append(Verse(
                        book=book, chapter=chapter, verse_number=verse_num,
                        translation=translation, text=text,
                    ))

        with transaction.atomic():
            Verse.objects.bulk_create(to_create, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(
            f'Loaded {len(to_create)} new verse(s) for {translation} '
            f'({total_in_file} verses found in file, {len(to_create)} were new).'
        ))
