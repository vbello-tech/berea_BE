from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # Enables Postgres's trigram similarity functions/operators
        # (similarity(), word_similarity(), the % operator, etc.) and the
        # gin_trgm_ops index class used below. Requires PostgreSQL with the
        # pg_trgm contrib module available (present by default on RDS,
        # Cloud SQL, most managed Postgres, and any standard install with
        # `CREATE EXTENSION` privileges).
        TrigramExtension(),
    ]
