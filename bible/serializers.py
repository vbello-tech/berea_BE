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


class WordTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = WordTag
        fields = ['position', 'original_word', 'transliteration', 'gloss', 'strongs_number', 'morphology']


class KjvStrongsTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = KjvStrongsTag
        fields = ['position', 'surface_word', 'original_word', 'transliteration', 'strongs_number', 'morphology']


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
    """
    Full verse shape: text plus every piece of study data at once. Kept for
    concordance_search_view, which returns a mixed list of verses from
    arbitrary places in scripture (not a single contiguous passage), so
    splitting reader/study data the way passage_view does wouldn't make
    sense there -- there's no separate "reader" fetch for search results.
    """
    book = serializers.CharField(source='book.name')
    concordance_entries = ConcordanceEntrySerializer(many=True, read_only=True)
    cross_references = CrossReferenceSerializer(many=True, read_only=True)
    word_tags = WordTagSerializer(many=True, read_only=True)
    kjv_strongs_tags = KjvStrongsTagSerializer(many=True, read_only=True)
    bulk_cross_references = serializers.SerializerMethodField()

    class Meta:
        model = Verse
        fields = [
            'id', 'book', 'chapter', 'verse_number', 'translation', 'text',
            'concordance_entries', 'cross_references', 'word_tags', 'kjv_strongs_tags',
            'bulk_cross_references',
        ]

    def get_bulk_cross_references(self, verse):
        limit = self.context.get('xref_limit', 10)
        qs = verse.bulk_cross_references.order_by('-votes')[:limit]
        return CrossReferenceLinkSerializer(qs, many=True).data


class VerseReaderSerializer(serializers.ModelSerializer):
    """
    Lightweight verse shape for the Scripture Reader: just the text needed
    to render the passage. No concordance/cross-reference/word-tag data --
    that's a separate, heavier fetch (VerseStudySerializer) so the reader
    can render as soon as this returns, without waiting on Study Suite data.
    """
    book = serializers.CharField(source='book.name')

    class Meta:
        model = Verse
        fields = ['id', 'book', 'chapter', 'verse_number', 'translation', 'text']


class VerseStudySerializer(serializers.ModelSerializer):
    """
    Study Suite data for a verse: concordance, cross-references, word tags.
    Keyed by verse_number so the frontend can merge this onto the
    already-rendered reader verses once it arrives.
    """
    concordance_entries = ConcordanceEntrySerializer(many=True, read_only=True)
    cross_references = CrossReferenceSerializer(many=True, read_only=True)
    word_tags = WordTagSerializer(many=True, read_only=True)
    kjv_strongs_tags = KjvStrongsTagSerializer(many=True, read_only=True)
    bulk_cross_references = serializers.SerializerMethodField()

    class Meta:
        model = Verse
        fields = [
            'verse_number', 'translation', 'concordance_entries', 'cross_references',
            'word_tags', 'kjv_strongs_tags', 'bulk_cross_references',
        ]

    def get_bulk_cross_references(self, verse):
        limit = self.context.get('xref_limit', 10)
        qs = verse.bulk_cross_references.order_by('-votes')[:limit]
        return CrossReferenceLinkSerializer(qs, many=True).data


