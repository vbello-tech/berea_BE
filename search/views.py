from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from bible.book_order import BOOK_ORDER_MAP
from bible.models import Verse

# Verses scoring below this are treated as noise rather than a genuine
# "this might be what you're thinking of" match, and dropped from the
# response even though the KNN ordering below always returns up to `limit`
# rows regardless of how weak the worst of them is.
MIN_SCORE = 0.15

# Case-insensitive lookup for book names, e.g. "1 john" -> "1 John". Built
# once at import time from the canonical book list already used elsewhere.
_BOOK_NAME_BY_LOWER = {name.lower(): name for name in BOOK_ORDER_MAP}


@api_view(['GET'])
@permission_classes([AllowAny])
def search_view(request):
    """
    GET /api/search/?q=<remembered text>&translation=KJV&limit=20
    Optional: &book=John  &testament=NT|OT

    For when someone can't recall a verse precisely. Uses Postgres's
    word_similarity() (pg_trgm) via the `<<->` KNN distance operator,
    backed by a GiST trigram index on Verse.text.

    Why word_similarity + GiST-KNN specifically, and not the more obvious
    options (verified by testing each against the real 31k-verse KJV table):

    - Plain trigram similarity() compares whole-string overlap, which
      penalizes a short remembered phrase against a much longer verse --
      John 3:16 scored *below* several irrelevant short verses when tested
      this way, because the verse's extra length dilutes the ratio.
    - word_similarity() instead finds the best-matching word-window within
      the (possibly longer) verse, which is the right semantics here --
      verified John 3:16 scores 1.0 for "for god so loved the world".
    - Using word_similarity() as a plain annotated function (not via this
      KNN operator) doesn't use any index -- measured at ~1.7s/query via
      EXPLAIN ANALYZE on this table.
    - Filtering with the `<%` threshold operator (also nominally
      index-backed) sounded right but the GIN trigram index isn't very
      selective for multi-word phrases against short verse text -- measured
      ~1.9s, since ~26,000 of 31,102 rows passed as "candidates" needing
      full rechecking.
    - This GiST + `<<->` KNN approach is what's actually fast: measured
      ~20-200ms across the full table, and correctly ranks exact matches,
      typos ("begining" -> Genesis 1:1), and vague thematic recall
      ("shepherd green pastures still waters" -> Psalm 23:2) all as the top
      result in testing.

    IMPORTANT: filters use exact equality, not __iexact, on purpose --
    verified via EXPLAIN ANALYZE that __iexact's UPPER(column) wrapping
    makes Postgres misestimate cardinality badly enough to flip the planner
    from the fast KNN index scan to a full sequential scan (714ms vs 20ms
    for the same query, differing only in that one lookup). Since the values
    compared here are small controlled vocabularies (translation codes,
    'OT'/'NT', and the 66 canonical book names), they're normalized in
    Python instead and compared with plain `=`.
    """
    query = request.query_params.get('q', '').strip()
    translation = request.query_params.get('translation', 'KJV').upper()
    book_param = request.query_params.get('book')
    testament = request.query_params.get('testament')
    try:
        limit = min(int(request.query_params.get('limit', 30)), 100)
    except ValueError:
        limit = 30

    if not query:
        return Response({'detail': 'Provide a q query param.'}, status=400)

    qs = Verse.objects.filter(translation=translation).select_related('book')

    if book_param:
        canonical_book = _BOOK_NAME_BY_LOWER.get(book_param.lower())
        if not canonical_book:
            return Response({'detail': f'Unknown book: {book_param}'}, status=400)
        qs = qs.filter(book__name=canonical_book)

    if testament:
        testament = testament.upper()
        if testament not in ('OT', 'NT'):
            return Response({'detail': "testament must be 'OT' or 'NT'."}, status=400)
        qs = qs.filter(book__testament=testament)

    # Django's ORM has no built-in expression for the word-similarity KNN
    # distance operator (`<<->`) -- TrigramWordSimilarity exists for
    # annotating/scoring, but ordering by it directly does not trigger the
    # KNN index path, only the raw operator does. .extra() is used here
    # specifically for that operator; everything else stays in the ORM.
    qs = qs.extra(
        select={'_distance': '%s <<-> text'},
        select_params=[query],
        order_by=['_distance'],
    )[:limit]

    results = []
    for v in qs:
        score = round(1 - v._distance, 4)
        if score < MIN_SCORE:
            continue
        results.append({
            'book': v.book.name,
            'chapter': v.chapter,
            'verse_number': v.verse_number,
            'text': v.text,
            'score': score,
        })

    return Response({'query': query, 'count': len(results), 'results': results})


