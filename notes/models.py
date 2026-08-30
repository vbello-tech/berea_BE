from django.conf import settings
from django.db import models


class Note(models.Model):
    """A user's personal study note attached to a passage reference."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notes')
    book = models.CharField(max_length=50)
    chapter = models.PositiveSmallIntegerField()
    verse_start = models.PositiveSmallIntegerField()
    verse_end = models.PositiveSmallIntegerField()
    text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'book', 'chapter', 'verse_start', 'verse_end')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user} note on {self.book} {self.chapter}:{self.verse_start}-{self.verse_end}"
