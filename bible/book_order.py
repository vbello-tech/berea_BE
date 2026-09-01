# Canonical order + testament for the 66-book Protestant Bible, keyed with
# the exact book names used in bible/fixtures/kjv/KJV_bible.json (note:
# "Psalm" singular, "Song Of Solomon", numbered books as "1 Samuel" etc.)

BOOK_ORDER = [
    ('Genesis', 'OT'), ('Exodus', 'OT'), ('Leviticus', 'OT'), ('Numbers', 'OT'),
    ('Deuteronomy', 'OT'), ('Joshua', 'OT'), ('Judges', 'OT'), ('Ruth', 'OT'),
    ('1 Samuel', 'OT'), ('2 Samuel', 'OT'), ('1 Kings', 'OT'), ('2 Kings', 'OT'),
    ('1 Chronicles', 'OT'), ('2 Chronicles', 'OT'), ('Ezra', 'OT'), ('Nehemiah', 'OT'),
    ('Esther', 'OT'), ('Job', 'OT'), ('Psalm', 'OT'), ('Proverbs', 'OT'),
    ('Ecclesiastes', 'OT'), ('Song Of Solomon', 'OT'), ('Isaiah', 'OT'), ('Jeremiah', 'OT'),
    ('Lamentations', 'OT'), ('Ezekiel', 'OT'), ('Daniel', 'OT'), ('Hosea', 'OT'),
    ('Joel', 'OT'), ('Amos', 'OT'), ('Obadiah', 'OT'), ('Jonah', 'OT'),
    ('Micah', 'OT'), ('Nahum', 'OT'), ('Habakkuk', 'OT'), ('Zephaniah', 'OT'),
    ('Haggai', 'OT'), ('Zechariah', 'OT'), ('Malachi', 'OT'),
    ('Matthew', 'NT'), ('Mark', 'NT'), ('Luke', 'NT'), ('John', 'NT'), ('Acts', 'NT'),
    ('Romans', 'NT'), ('1 Corinthians', 'NT'), ('2 Corinthians', 'NT'), ('Galatians', 'NT'),
    ('Ephesians', 'NT'), ('Philippians', 'NT'), ('Colossians', 'NT'),
    ('1 Thessalonians', 'NT'), ('2 Thessalonians', 'NT'), ('1 Timothy', 'NT'),
    ('2 Timothy', 'NT'), ('Titus', 'NT'), ('Philemon', 'NT'), ('Hebrews', 'NT'),
    ('James', 'NT'), ('1 Peter', 'NT'), ('2 Peter', 'NT'), ('1 John', 'NT'),
    ('2 John', 'NT'), ('3 John', 'NT'), ('Jude', 'NT'), ('Revelation', 'NT'),
]

BOOK_ORDER_MAP = {name: (i + 1, testament) for i, (name, testament) in enumerate(BOOK_ORDER)}

# Case-insensitive lookup, e.g. "1 john" -> "1 John". Used wherever a book
# name arrives from a query param and needs normalizing to the canonical
# name for an exact-match DB filter -- avoids Django's __iexact lookup,
# which wraps the column in UPPER(...) and can badly distort Postgres's
# query planning on larger tables (verified on Verse: an __iexact filter
# combined with ordering flipped an index scan into a sequential scan,
# ~700ms vs ~20ms for an otherwise-identical query).
BOOK_NAME_BY_LOWER = {name.lower(): name for name in BOOK_ORDER_MAP}
