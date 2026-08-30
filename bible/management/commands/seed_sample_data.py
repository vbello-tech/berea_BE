from django.core.management.base import BaseCommand
from bible.models import Book, Verse, ConcordanceEntry, CrossReference, StrongsEntry

# NOTE: This is a small starter set (the same 4 passages used in the demo
# frontend) so you can see the whole pipeline working end to end. The KJV
# text is public domain -- to load the full Bible, source a KJV text file
# (e.g. a plain-text or JSON KJV dump) and adapt the DATA structure below,
# or write a loader that parses that file directly.

DATA = [
    {
        'book': 'John', 'testament': 'NT', 'order': 43, 'chapter': 3,
        'verses': [
            {
                'num': 16,
                'text': 'For God so loved the world, that he gave his only begotten Son, '
                        'that whosoever believeth in him should not perish, but have everlasting life.',
                'concordance': [
                    ('loved', 'agapa\u014d (\u1f00\u03b3\u03b1\u03c0\u03ac\u03c9)', 'G25', '143+'),
                    ('world', 'kosmos (\u03ba\u03cc\u03c3\u03bc\u03bf\u03c2)', 'G2889', '186+'),
                    ('gave', 'did\u014dmi (\u03b4\u03af\u03b4\u03c9\u03bc\u03b9)', 'G1325', '415+'),
                    ('begotten', 'monogen\u0113s (\u03bc\u03bf\u03bd\u03bf\u03b3\u03b5\u03bd\u03ae\u03c2)', 'G3439', '9'),
                    ('Son', 'huios (\u03c5\u1f31\u03cc\u03c2)', 'G5207', '370+'),
                    ('believeth', 'pisteu\u014d (\u03c0\u03b9\u03c3\u03c4\u03b5\u03cd\u03c9)', 'G4100', '241+'),
                    ('perish', 'apollymi (\u1f00\u03c0\u03cc\u03bb\u03bb\u03c5\u03bc\u03b9)', 'G622', '92'),
                    ('everlasting', 'ai\u014dnios (\u03b1\u1f30\u03ce\u03bd\u03b9\u03bf\u03c2)', 'G166', '71'),
                    ('life', 'z\u014d\u0113 (\u03b6\u03c9\u03ae)', 'G2222', '135'),
                ],
                'crossrefs': [
                    ('Romans 5:8', "God's Love", 'But God commendeth his love toward us, in that, while we were yet sinners, Christ died for us.'),
                    ('1 John 4:9', 'Only Begotten', 'In this was manifested the love of God toward us, because that God sent his only begotten Son into the world, that we might live through him.'),
                ],
            },
            {
                'num': 17,
                'text': 'For God sent not his Son into the world to condemn the world; '
                        'but that the world through him might be saved.',
                'concordance': [
                    ('sent', 'apostell\u014d (\u1f00\u03c0\u03bf\u03c3\u03c4\u03ad\u03bb\u03bb\u03c9)', 'G649', '132'),
                    ('condemn', 'krin\u014d (\u03ba\u03c1\u03af\u03bd\u03c9)', 'G2919', '114'),
                    ('saved', 's\u014dz\u014d (\u03c3\u1ff4\u03b6\u03c9)', 'G4982', '106'),
                ],
                'crossrefs': [],
            },
        ],
    },
    {
        'book': 'Romans', 'testament': 'NT', 'order': 45, 'chapter': 8,
        'verses': [
            {
                'num': 28,
                'text': 'And we know that all things work together for good to them that love God, '
                        'to them who are the called according to his purpose.',
                'concordance': [
                    ('work', 'synergeo (\u03c3\u03c5\u03bd\u03b5\u03c1\u03b3\u03ad\u03c9)', 'G4903', '5'),
                    ('good', 'agathos (\u1f00\u03b3\u03b1\u03b8\u03cc\u03c2)', 'G18', '102'),
                    ('love', 'agapa\u014d (\u1f00\u03b3\u03b1\u03c0\u03ac\u03c9)', 'G25', '143+'),
                    ('called', 'kl\u0113tos (\u03ba\u03bb\u03b7\u03c4\u03cc\u03c2)', 'G2822', '11'),
                ],
                'crossrefs': [
                    ('Genesis 50:20', "God's Purpose", 'But as for you, ye thought evil against me; but God meant it unto good.'),
                    ('Ephesians 1:11', 'Predestination', 'Being predestinated according to the purpose of him who worketh all things after the counsel of his own will.'),
                ],
            },
        ],
    },
    {
        'book': 'Psalm', 'testament': 'OT', 'order': 19, 'chapter': 23,
        'verses': [
            {
                'num': 1, 'text': 'The LORD is my shepherd; I shall not want.',
                'concordance': [
                    ('shepherd', "ra'ah (\u05e8\u05b8\u05e2\u05b8\u05d4)", 'H7462', '173'),
                    ('want', 'chaser (\u05d7\u05b8\u05e1\u05b5\u05e8)', 'H2637', '19'),
                ],
                'crossrefs': [('John 10:11', 'Good Shepherd', 'I am the good shepherd: the good shepherd giveth his life for the sheep.')],
            },
            {
                'num': 2, 'text': 'He maketh me to lie down in green pastures: he leadeth me beside the still waters.',
                'concordance': [], 'crossrefs': [],
            },
            {
                'num': 3, 'text': "He restoreth my soul: he leadeth me in the paths of righteousness for his name's sake.",
                'concordance': [('restoreth', 'shuwb (\u05e9\u05c1\u05d5\u05bc\u05d1)', 'H7725', '1060+')],
                'crossrefs': [('Ezekiel 34:15', 'Shepherd Imagery', 'I will feed my flock, and I will cause them to lie down, saith the Lord GOD.')],
            },
        ],
    },
    {
        'book': 'Genesis', 'testament': 'OT', 'order': 1, 'chapter': 1,
        'verses': [
            {
                'num': 1, 'text': 'In the beginning God created the heaven and the earth.',
                'concordance': [('created', 'bara (\u05d1\u05bc\u05b8\u05e8\u05b8\u05d0)', 'H1254', '54')],
                'crossrefs': [('John 1:1', 'Creation / Logos', 'In the beginning was the Word, and the Word was with God, and the Word was God.')],
            },
            {
                'num': 2,
                'text': 'And the earth was without form, and void; and darkness was upon the face of the deep. '
                        'And the Spirit of God moved upon the face of the waters.',
                'concordance': [], 'crossrefs': [],
            },
            {
                'num': 3, 'text': 'And God said, Let there be light: and there was light.',
                'concordance': [('light', 'owr (\u05d0\u05d5ֹר)', 'H216', '120+')],
                'crossrefs': [('Hebrews 11:3', 'Creation by Faith', 'Through faith we understand that the worlds were framed by the word of God.')],
            },
        ],
    },
]


class Command(BaseCommand):
    help = 'Load a small starter set of public-domain KJV passages, concordance entries, and cross references.'

    def handle(self, *args, **options):
        created_verses = 0
        for book_data in DATA:
            book, _ = Book.objects.get_or_create(
                name=book_data['book'],
                defaults={'order': book_data['order'], 'testament': book_data['testament']},
            )
            for v in book_data['verses']:
                verse, created = Verse.objects.get_or_create(
                    book=book,
                    chapter=book_data['chapter'],
                    verse_number=v['num'],
                    translation='KJV',
                    defaults={'text': v['text']},
                )
                if created:
                    created_verses += 1

                # Attach concordance/cross-ref data whenever it's missing,
                # regardless of whether the verse itself already existed
                # (e.g. because the full Bible was loaded first).
                if not verse.concordance_entries.exists():
                    for term, original, strongs, count in v['concordance']:
                        ConcordanceEntry.objects.create(
                            verse=verse, english_term=term, original_word=original,
                            strongs_number=strongs, occurrence_count=count,
                            strongs_entry=StrongsEntry.objects.filter(number__iexact=strongs).first(),
                        )
                if not verse.cross_references.exists():
                    for ref, tag, text in v['crossrefs']:
                        CrossReference.objects.create(
                            verse=verse, reference_label=ref, tag=tag, text=text,
                        )

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {created_verses} verse(s) across {len(DATA)} book/chapter group(s).'
        ))
