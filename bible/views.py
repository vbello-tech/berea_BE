from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import re

from .book_order import BOOK_NAME_BY_LOWER
from .models import Verse, StrongsEntry
from .serializers import VerseSerializer, StrongsEntrySerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def passage_view(request):
    """
    GET /api/passage/?book=John&chapter=3&start=16&end=17&translation=KJV
    GET /api/passage/?book=John&chapter=3&translation=KJV
        (start/end omitted -> returns the entire chapter)

    Returns the verses in the given range (or the whole chapter, if start
    is omitted), each with its concordance entries, cross references, and
    word tags nested inline.

    Book names and translation codes are normalized in Python and matched
    with exact equality rather than Django's __iexact lookup. __iexact
    wraps the column in UPPER(...), and on this same project's search
    endpoint that was measured (via EXPLAIN ANALYZE) to make Postgres
    badly misestimate row counts and fall back to a sequential scan instead
    of the index on (book, chapter, verse_number, translation) -- ~700ms
    vs ~20ms for an otherwise-identical query. Since book names and
    translation codes are both small, known vocabularies, normalizing them
    in Python and comparing with `=` avoids the problem entirely while
    also giving a clearer 400 for a genuinely unknown book, instead of a
    404 that could be mistaken for "this chapter/verse doesn't exist".
    """
    book_param = request.query_params.get('book')
    chapter = request.query_params.get('chapter')
    start = request.query_params.get('start')
    end = request.query_params.get('end', start)
    translation = request.query_params.get('translation', 'KJV').upper()
    xref_limit = int(request.query_params.get('xref_limit', 10))

    if not (book_param and chapter):
        return Response(
            {'detail': 'book and chapter query params are required '
                       '(start/end are optional -- omit both to get the whole chapter).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    canonical_book = BOOK_NAME_BY_LOWER.get(book_param.lower())
    if not canonical_book:
        return Response({'detail': f'Unknown book: {book_param}'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        chapter = int(chapter)
    except ValueError:
        return Response({'detail': 'chapter must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

    verses = Verse.objects.filter(book__name=canonical_book, chapter=chapter, translation=translation)

    if start is not None:
        try:
            start = int(start)
            end = int(end)
        except ValueError:
            return Response({'detail': 'start/end must be integers.'}, status=status.HTTP_400_BAD_REQUEST)
        verses = verses.filter(verse_number__gte=start, verse_number__lte=end)

    verses = list(
        verses.select_related('book')
        .prefetch_related('concordance_entries', 'cross_references', 'word_tags', 'bulk_cross_references')
        .order_by('verse_number')
    )

    if not verses:
        range_desc = f'{start}-{end}' if start is not None else 'whole chapter'
        return Response(
            {'detail': f'No verses found for {canonical_book} {chapter}:{range_desc} ({translation}).'},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = VerseSerializer(verses, many=True, context={'xref_limit': xref_limit})
    return Response({'results': serializer.data})


@api_view(['GET'])
@permission_classes([AllowAny])
def concordance_search_view(request):
    """GET /api/concordance/?term=loved  or  ?strongs=G25"""
    term = request.query_params.get('term')
    strongs = request.query_params.get('strongs')

    verses = Verse.objects.all()
    if term:
        verses = verses.filter(concordance_entries__english_term__icontains=term)
    if strongs:
        verses = verses.filter(concordance_entries__strongs_number=strongs.upper())

    verses = verses.distinct().select_related('book').prefetch_related(
        'concordance_entries', 'cross_references'
    )
    serializer = VerseSerializer(verses, many=True)
    return Response({'results': serializer.data})


def _word_forms(word):
    """Very small stemmer so 'loved'/'loves'/'loving' all match an entry keyed on 'love'."""
    word = word.lower().strip()
    forms = {word}
    for suffix in ('ing', 'edst', 'edest', 'eth', 'est', 'ed', 'es', 's'):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            forms.add(word[: -len(suffix)])
    return forms


def _split_senses(text):
    """
    Strong's definitions bundle multiple senses into one string, separated
    by semicolons (the most common separator in this lexicon), e.g.
    'orderly arrangement, i.e. decoration; by implication, the world...'
    Splitting on ';' gives a rough but usable list of distinct senses so a
    single ambiguous entry can be displayed as separate meanings rather
    than one undifferentiated blob.
    """
    if not text:
        return []
    return [s.strip() for s in text.split(';') if s.strip()]


def _match_quality(entry, word, forms):
    """
    Rank how well an entry matches the queried word, so an exact whole-word
    match (e.g. 'loved' -> '(be-)love(-ed)') ranks above a looser stemmed
    match. This doesn't resolve which sense applies at a given verse -- it
    only orders candidates so the closer matches surface first.
    """
    kjv_def_lower = entry.kjv_def.lower()
    word_lower = word.lower()
    if re.search(rf'\b{re.escape(word_lower)}\b', kjv_def_lower):
        return 2  # exact form appears as its own word
    for form in forms:
        if re.search(rf'\b{re.escape(form)}\b', kjv_def_lower):
            return 1  # a stemmed root matches, but not the exact form typed
    return 0  # matched only via substring/regex, weakest signal


@api_view(['GET'])
@permission_classes([AllowAny])
def strongs_lookup_view(request):
    """
    GET /api/strongs/?number=G25          -> exact lexicon entry
    GET /api/strongs/?word=loved          -> reverse lookup: which Greek/Hebrew
                                              entries render this English word
                                              in the KJV (Strong's own method,
                                              since we don't have a verse-tagged text)

    When a word maps to multiple Strong's numbers (true polysemy -- e.g.
    "world" renders 6 different Greek words), all candidates are returned,
    ranked by match quality, each with its definition broken into distinct
    senses. This endpoint deliberately does NOT pick one for you: without a
    Strong's-tagged text there's no reliable way to know which sense applies
    at a specific verse, so the ambiguity is surfaced rather than hidden.
    """
    number = request.query_params.get('number')
    word = request.query_params.get('word')

    if number:
        try:
            entry = StrongsEntry.objects.get(number=number.upper())
        except StrongsEntry.DoesNotExist:
            return Response({'detail': f'No Strongs entry for {number}.'}, status=404)
        data = StrongsEntrySerializer(entry).data
        data['senses'] = _split_senses(entry.strongs_def)
        return Response(data)

    if word:
        forms = _word_forms(word)
        pattern = '|'.join(re.escape(f) for f in forms)
        regex = re.compile(pattern, re.IGNORECASE)

        candidates = StrongsEntry.objects.filter(kjv_def__iregex=pattern)
        matches = [e for e in candidates if regex.search(e.kjv_def)]

        # Rank so exact-form matches (e.g. "loved" itself, not just "love")
        # come first, then attach a broken-out sense list to each result.
        ranked = sorted(matches, key=lambda e: -_match_quality(e, word, forms))
        results = []
        for e in ranked:
            row = StrongsEntrySerializer(e).data
            row['senses'] = _split_senses(e.strongs_def)
            row['match_quality'] = _match_quality(e, word, forms)
            results.append(row)

        return Response({
            'query': word,
            'ambiguous': len(results) > 1,
            'note': "Matches are based on the King James Version's rendering of each "
                    "original-language word (per Strong's own concordance method), not "
                    "a verse-by-verse tagging. When more than one entry is returned, the "
                    "word genuinely translates multiple distinct original-language words "
                    "(true polysemy) -- these are ranked by match quality but not resolved "
                    "to a single 'correct' one, since that requires knowing the specific "
                    "verse and a tagged text to confirm.",
            'results': results,
        })

    return Response({'detail': 'Provide a number or word query param.'}, status=400)


