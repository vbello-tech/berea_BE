from django.db import models


class StrongsEntry(models.Model):
    """
    A single entry from the Strong's Greek/Hebrew lexicon (definitions only,
    not tied to any specific verse occurrence). Sourced from
    https://github.com/openscriptures/strongs
    """
    LANGUAGE_CHOICES = [('greek', 'Greek'), ('hebrew', 'Hebrew')]

    number = models.CharField(max_length=10, unique=True, help_text="e.g. G25 or H1254")
    language = models.CharField(max_length=6, choices=LANGUAGE_CHOICES)
    lemma = models.CharField(max_length=100, blank=True, help_text="Word in original script")
    translit = models.CharField(max_length=100, blank=True, help_text="Transliteration")
    pronunciation = models.CharField(max_length=100, blank=True)
    derivation = models.TextField(blank=True)
    strongs_def = models.TextField(blank=True, help_text="Strong's own definition")
    kjv_def = models.TextField(
        blank=True,
        help_text="How the KJV renders this word, e.g. '(be-)love(-ed)'. "
                   "Used for reverse word-lookup since we don't have a "
                   "verse-tagged text.",
    )

    class Meta:
        indexes = [models.Index(fields=['number'])]
        verbose_name_plural = 'Strongs entries'

    def __str__(self):
        return f"{self.number} ({self.lemma})"


class Book(models.Model):
    """A book of the Bible, e.g. 'John', 'Genesis'."""
    name = models.CharField(max_length=50, unique=True)
    order = models.PositiveSmallIntegerField(help_text="Canonical order, Genesis=1")
    testament = models.CharField(
        max_length=3,
        choices=[('OT', 'Old Testament'), ('NT', 'New Testament')],
    )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class Verse(models.Model):
    """A single verse of scripture in a given translation."""
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='verses')
    chapter = models.PositiveSmallIntegerField()
    verse_number = models.PositiveSmallIntegerField()
    translation = models.CharField(max_length=10, default='KJV')
    text = models.TextField(help_text="Plain verse text, no markup")

    class Meta:
        unique_together = ('book', 'chapter', 'verse_number', 'translation')
        ordering = ['book__order', 'chapter', 'verse_number']
        indexes = [
            models.Index(fields=['book', 'chapter', 'verse_number', 'translation']),
        ]

    def __str__(self):
        return f"{self.book.name} {self.chapter}:{self.verse_number} ({self.translation})"


class ConcordanceEntry(models.Model):
    """Maps an English word as it appears in a specific verse to its original-language term."""
    verse = models.ForeignKey(Verse, on_delete=models.CASCADE, related_name='concordance_entries')
    english_term = models.CharField(max_length=50)
    original_word = models.CharField(max_length=100, help_text="e.g. 'agapa\u014d (\u1f00\u03b3\u03b1\u03c0\u03ac\u03c9)'")
    strongs_number = models.CharField(max_length=10, help_text="e.g. G25 or H7462")
    occurrence_count = models.CharField(
        max_length=10,
        help_text="Display string for total occurrences across scripture, e.g. '143+'",
    )
    strongs_entry = models.ForeignKey(
        StrongsEntry, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='concordance_entries',
        help_text="Optional link to the full lexicon entry for richer display",
    )

    class Meta:
        indexes = [models.Index(fields=['strongs_number']), models.Index(fields=['english_term'])]

    def __str__(self):
        return f"{self.english_term} -> {self.strongs_number}"


class CrossReference(models.Model):
    """A related verse reference shown alongside a given verse."""
    verse = models.ForeignKey(Verse, on_delete=models.CASCADE, related_name='cross_references')
    reference_label = models.CharField(max_length=60, help_text="e.g. 'Romans 5:8'")
    tag = models.CharField(max_length=60, help_text="Short theme label, e.g. \"God's Love\"")
    text = models.TextField()

    def __str__(self):
        return f"{self.verse} -> {self.reference_label}"


class CrossReferenceLink(models.Model):
    """
    A single cross-reference from the OpenBible.info dataset (CC BY 4.0,
    primarily sourced from the public-domain Treasury of Scripture
    Knowledge). Unlike CrossReference (a handful of hand-curated,
    thematically-tagged references), this is the full ~344,800-row public
    dataset with a crowd-sourced relevance score ("votes") but no theme tag.

    The "to" side may be a range, and in rare cases (~18 of 344,800) that
    range spans a book boundary (e.g. 2 Chronicles 36 -> Ezra 1), so start
    and end are stored as fully independent book/chapter/verse fields
    rather than assuming they share a book or chapter.
    """
    from_verse = models.ForeignKey(
        Verse, on_delete=models.CASCADE, related_name='bulk_cross_references',
        help_text="The verse this cross-reference is attached to",
    )
    to_book_start = models.CharField(max_length=50)
    to_chapter_start = models.PositiveSmallIntegerField()
    to_verse_start = models.PositiveSmallIntegerField()
    to_book_end = models.CharField(max_length=50)
    to_chapter_end = models.PositiveSmallIntegerField()
    to_verse_end = models.PositiveSmallIntegerField()
    votes = models.IntegerField(help_text="Crowd-sourced relevance score; can be negative")

    class Meta:
        ordering = ['-votes']
        indexes = [models.Index(fields=['from_verse', '-votes'])]

    @property
    def to_reference_label(self):
        start = f"{self.to_book_start} {self.to_chapter_start}:{self.to_verse_start}"
        if self.to_book_start == self.to_book_end and self.to_chapter_start == self.to_chapter_end:
            if self.to_verse_start == self.to_verse_end:
                return start
            return f"{start}-{self.to_verse_end}"
        if self.to_book_start == self.to_book_end:
            return f"{start}-{self.to_chapter_end}:{self.to_verse_end}"
        return f"{start}-{self.to_book_end} {self.to_chapter_end}:{self.to_verse_end}"

    def __str__(self):
        return f"{self.from_verse} -> {self.to_reference_label} ({self.votes} votes)"


class WordTag(models.Model):
    """
    A single original-language word occurrence within a specific verse,
    tagged with its exact Strong's number. Unlike ConcordanceEntry (hand
    curated) or the /api/strongs/?word= reverse lookup (unresolved
    candidates), this is real word-by-word tagging sourced from a
    Strong's-tagged text (STEPBible-Data's TAGNT), so it resolves
    ambiguity: e.g. it can say the "world" in John 3:16 specifically is
    G2889, not one of the other 5 Greek words KJV also renders "world".
    """
    verse = models.ForeignKey(Verse, on_delete=models.CASCADE, related_name='word_tags')
    position = models.PositiveSmallIntegerField(help_text="Word order within the original-language verse")
    original_word = models.CharField(max_length=100, help_text="Greek/Hebrew word as it appears, with accents")
    transliteration = models.CharField(max_length=100, blank=True)
    gloss = models.CharField(max_length=200, blank=True, help_text="English gloss for this specific word occurrence")
    strongs_number = models.CharField(max_length=10, help_text="e.g. G2889")
    morphology = models.CharField(max_length=50, blank=True, help_text="Parsing code, e.g. N-ASM")
    strongs_entry = models.ForeignKey(
        StrongsEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='word_tags'
    )

    class Meta:
        ordering = ['verse', 'position']
        indexes = [models.Index(fields=['verse', 'position']), models.Index(fields=['strongs_number'])]

    def __str__(self):
        return f"{self.verse} #{self.position}: {self.original_word} ({self.strongs_number})"

