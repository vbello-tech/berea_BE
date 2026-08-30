from django.contrib import admin
from .models import Book, Verse, ConcordanceEntry, CrossReference, StrongsEntry, WordTag, CrossReferenceLink


@admin.register(CrossReferenceLink)
class CrossReferenceLinkAdmin(admin.ModelAdmin):
    list_display = ('from_verse', 'to_reference_label', 'votes')
    search_fields = ('from_verse__book__name',)
    list_filter = ('votes',)


@admin.register(StrongsEntry)
class StrongsEntryAdmin(admin.ModelAdmin):
    list_display = ('number', 'language', 'lemma', 'translit', 'kjv_def')
    list_filter = ('language',)
    search_fields = ('number', 'lemma', 'translit', 'kjv_def')


class WordTagInline(admin.TabularInline):
    model = WordTag
    extra = 0
    readonly_fields = ('position', 'original_word', 'transliteration', 'gloss', 'strongs_number', 'morphology')
    can_delete = False


class ConcordanceEntryInline(admin.TabularInline):
    model = ConcordanceEntry
    extra = 1


class CrossReferenceInline(admin.TabularInline):
    model = CrossReference
    extra = 1


@admin.register(Verse)
class VerseAdmin(admin.ModelAdmin):
    list_display = ('book', 'chapter', 'verse_number', 'translation')
    list_filter = ('book', 'translation')
    inlines = [WordTagInline, ConcordanceEntryInline, CrossReferenceInline]


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'testament')


admin.site.register(ConcordanceEntry)
admin.site.register(CrossReference)

