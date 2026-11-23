from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, resolve_url
from django.urls import reverse
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import HandoffToken
from .permissions import HasScope

PROFILE_FIELDS = ('first_name', 'last_name', 'email')


class UnknownRole(ValueError):
    """Raised by a system's role hook when the hub sends a level it does not have."""


def _role_hook():
    path = getattr(settings, 'JM_CONNECT_APPLY_ROLE', '')
    return import_string(path) if path else None


def _find_or_create(data):
    User = get_user_model()
    username = data.get('username', '')
    user = User.objects.filter(username=username).first()
    if user is None and username and getattr(settings, 'JM_CONNECT_CREATE_USERS', False):
        profile = {field: str(data.get(field) or '')[:150] for field in PROFILE_FIELDS}
        user = User.objects.create_user(username=username, password=None, **profile)
    return user if user is not None and user.is_active else None


class HandoffView(APIView):
    """The hub's server asks for a one-time sign-in link for a username, with the person's level here."""

    authentication_classes = []
    permission_classes = [HasScope]
    required_scope = 'handoff'

    def post(self, request):
        role = str(request.data.get('role') or '')
        hook = _role_hook()
        try:
            with transaction.atomic():
                user = _find_or_create(request.data)
                if user is None:
                    return Response({'error': 'No active account with that username.'}, status=404)
                if role and hook:
                    hook(user, role)
        except UnknownRole:
            return Response({'error': 'This system has no such level.'}, status=400)
        path = reverse('jm_connect:enter', args=[HandoffToken.issue(user)])
        return Response({'url': request.build_absolute_uri(path)})


@never_cache
def enter(request, token):
    """The person's browser arrives here from the hub. The link works once."""
    user = HandoffToken.redeem(token)
    if user is None:
        return HttpResponse(
            'This sign-in link has expired or was already used. Please go back to JM Hub and try again.',
            status=410,
            content_type='text/plain',
        )
    login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
    response = redirect(resolve_url(settings.LOGIN_REDIRECT_URL))
    response['Referrer-Policy'] = 'no-referrer'
    return response
