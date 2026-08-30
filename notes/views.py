from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Note
from .serializers import NoteSerializer


class NoteViewSet(viewsets.ModelViewSet):
    """
    Standard CRUD at /api/notes/ (list, create, retrieve, update, delete),
    always scoped to the authenticated user.

    Plus a convenience endpoint:
    GET/PUT /api/notes/by_passage/?book=John&chapter=3&start=16&end=17
    which gets-or-creates the note for that exact passage so the frontend
    doesn't need to know the note's id ahead of time.
    """
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Note.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get', 'put'])
    def by_passage(self, request):
        book = request.query_params.get('book')
        chapter = request.query_params.get('chapter')
        start = request.query_params.get('start')
        end = request.query_params.get('end', start)

        if not (book and chapter and start):
            return Response(
                {'detail': 'book, chapter, and start query params are required.'},
                status=400,
            )

        note, _created = Note.objects.get_or_create(
            user=request.user,
            book=book,
            chapter=chapter,
            verse_start=start,
            verse_end=end,
            defaults={'text': ''},
        )

        if request.method == 'PUT':
            note.text = request.data.get('text', '')
            note.save()

        return Response(NoteSerializer(note).data)
