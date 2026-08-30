from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

User = get_user_model()


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """POST /api/auth/register/ {username, email, password} -> {token, username}"""
    username = request.data.get('username', '').strip()
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '')

    if not username or not password:
        return Response({'detail': 'username and password are required.'}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({'detail': 'That username is already taken.'}, status=400)

    try:
        validate_password(password)
    except DjangoValidationError as e:
        return Response({'detail': list(e.messages)}, status=400)

    user = User.objects.create_user(username=username, email=email, password=password)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'username': user.username}, status=status.HTTP_201_CREATED)


class LoginView(ObtainAuthToken):
    """POST /api/auth/login/ {username, password} -> {token, username}"""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        token = Token.objects.get(key=response.data['token'])
        response.data['username'] = token.user.username
        return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """POST /api/auth/logout/ -> deletes the current token"""
    request.user.auth_token.delete()
    return Response({'detail': 'Logged out.'})
