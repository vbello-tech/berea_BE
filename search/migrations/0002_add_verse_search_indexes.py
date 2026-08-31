from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0001_enable_pg_trgm'),
        ('bible', '0001_initial'),
    ]

    operations = [
        # Trigram GIN index on Verse.text -- backs TrigramSimilarity /
        # TrigramWordSimilarity lookups so fuzzy/rough-recall search is fast
        # even across the full 31k+ verse table.
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS bible_verse_text_trgm_idx
                ON bible_verse USING GIN (text gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS bible_verse_text_trgm_idx;",
        ),
        # Full-text search GIN index. The expression must match what Django's
        # SearchVector('text', config='english') generates at query time --
        # which wraps the column in COALESCE(text, '') -- or Postgres won't
        # recognize the index as usable for that query (expression indexes
        # require a matching expression, not just semantic equivalence).
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS bible_verse_text_fts_idx
                ON bible_verse USING GIN (to_tsvector('english', COALESCE(text, '')));
            """,
            reverse_sql="DROP INDEX IF EXISTS bible_verse_text_fts_idx;",
        ),
    ]
