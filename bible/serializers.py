from itertools import groupby

from rest_framework import serializers
from .models import Verse, ConcordanceEntry, CrossReference, StrongsEntry, WordTag, CrossReferenceLink, KjvStrongsTag


class CrossReferenceLinkSerializer(serializers.ModelSerializer):
    reference_label = serializers.CharField(source='to_reference_label')

    class Meta:
        model = CrossReferenceLink
        fields = ['reference_label', 'votes']


class StrongsEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = StrongsEntry
        fields = [
            'number', 'language', 'lemma', 'translit', 'pronunciation',
            'derivation', 'strongs_def', 'kjv_def',
        ]


# ---------------------------------------------------------------------------
# WordTagSerializer / KjvStrongsTagSerializer are no longer used directly as
# fields on VerseSerializer -- word_tags is now built by
# _group_tags_by_position below and is the SAME regardless of which
# translation is being read (no per-translation filtering: changing the
# Bible version must not change what the interlinear shows). kjv_render_text
# is still fetched (harmless to keep in the payload) but nothing filters on
# it anymore. kjv_strongs_tags is no longer part of the response at all.
# The KjvStrongsTag model/table and its loader command
# (load_kjv_strongs_richtags) are untouched and still exist; they're just
# not queried here. Left commented out in case anything else in the
# codebase imports these serializers directly.
# ---------------------------------------------------------------------------
# class WordTagSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = WordTag
#         fields = ['position', 'original_word', 'transliteration', 'gloss', 'strongs_number', 'morphology', 'kjv_render_text']
#
#
# class KjvStrongsTagSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = KjvStrongsTag
#         fields = ['position', 'surface_word', 'original_word', 'transliteration', 'strongs_number', 'morphology']


def _group_tags_by_position(tags, extra_fields):
    """
    Some source rows (TAHOT/TAGNT-derived) tag one original-language word
    with a compound Strong's field, e.g. "H0853/H01254" -- an untranslated
    object marker folded onto the nearest content word (see Gen.1.1#03:
    Hebrew "et" H0853 alongside the verb H01254 "created"). These load as
    multiple WordTag rows sharing one `position`. Collapse those back into
    one dict per position, with strongs_number as a list, so the frontend
    renders one interlinear row per original word/phrase instead of one
    row per Strong's number.

    `tags` must already be an iterable of model instances (e.g. from a
    prefetch_related cache via `.all()`) -- this function does not query
    the DB.
    `extra_fields` are the scalar field names (besides position and
    strongs_number) to copy from the first row in each group -- these are
    expected to be identical across all rows in a group.
    """
    ordered = sorted(tags, key=lambda t: (t.position, t.id))
    result = []
    for position, group in groupby(ordered, key=lambda t: t.position):
        group = list(group)
        first = group[0]
        row = {'position': position, 'strongs_number': [t.strongs_number for t in group]}
        for field in extra_fields:
            row[field] = getattr(first, field)
        result.append(row)
    return result


class ConcordanceEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ConcordanceEntry
        fields = ['english_term', 'original_word', 'strongs_number', 'occurrence_count']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # A ConcordanceEntry attached directly to this verse is a curated,
        # human-confirmed mapping for this specific occurrence -- unlike the
        # /api/strongs/?word= reverse lookup, which can only list candidates.
        data['confirmed_for_this_verse'] = True
        return data


class CrossReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrossReference
        fields = ['reference_label', 'tag', 'text']


class VerseSerializer(serializers.ModelSerializer):
    book = serializers.CharField(source='book.name')
    concordance_entries = ConcordanceEntrySerializer(many=True, read_only=True)
    cross_references = CrossReferenceSerializer(many=True, read_only=True)

    # --- was ---
    # word_tags = WordTagSerializer(many=True, read_only=True)
    # kjv_strongs_tags = KjvStrongsTagSerializer(many=True, read_only=True)
    # --- now: word_tags alone, sourced via context (see passage_view),
    # grouped by position, identical regardless of translation.
    # kjv_strongs_tags is no longer part of the response. ---
    word_tags = serializers.SerializerMethodField()

    bulk_cross_references = serializers.SerializerMethodField()

    class Meta:
        model = Verse
        fields = [
            'id', 'book', 'chapter', 'verse_number', 'translation', 'text',
            'concordance_entries', 'cross_references', 'word_tags',
            # 'kjv_strongs_tags',  -- removed, see above
            'bulk_cross_references',
        ]

    def get_word_tags(self, verse):
        # word_tags is only ever loaded onto BSB Verse rows in the DB, so
        # passage_view fetches it separately (always via the matching BSB
        # verse, by verse_number) and hands it in through context rather
        # than via verse.word_tags.all() -- that relation is empty for any
        # non-BSB verse instance. No per-translation filtering: this
        # returns the same list regardless of verse.translation, by design
        # -- switching Bible versions in the reader must not change the
        # interlinear.
        word_tags_map = self.context.get('word_tags_by_verse_number', {})
        tags = word_tags_map.get(verse.verse_number, [])
        return _group_tags_by_position(
            tags,
            extra_fields=['original_word', 'transliteration', 'gloss', 'morphology', 'kjv_render_text'],
        )

    def get_bulk_cross_references(self, verse):
        limit = self.context.get('xref_limit', 10)
        qs = verse.bulk_cross_references.order_by('-votes')[:limit]
        return CrossReferenceLinkSerializer(qs, many=True).data


