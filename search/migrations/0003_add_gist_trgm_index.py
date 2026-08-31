from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0002_add_verse_search_indexes'),
    ]

    operations = [
        # GiST trigram index -- required for the `<<->` word_similarity KNN
        # operator used by the search view for fast top-N fuzzy matching.
        # This is a different index type from the GIN trigram index added
        # in the previous migration: GIN backs threshold operators (%, <%)
        # but not KNN ordering; only GiST supports the `<<->` distance
        # operator's index-assisted path. Verified via EXPLAIN ANALYZE this
        # is what actually makes fuzzy "remembered phrase" search fast
        # (~180-200ms) rather than falling back to a near-full scan.
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS bible_verse_text_gist_trgm_idx
                ON bible_verse USING GIST (text gist_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS bible_verse_text_gist_trgm_idx;",
        ),
    ]
