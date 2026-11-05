from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.http import HttpResponse
from django.shortcuts import redirect, resolve_url
from django.urls import reverse
from django.views.decorators.cache import never_cache
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import HandoffToken
from .permissions import HasScope


class HandoffView(APIView):
    """The hub's server asks for a one-time sign-in link for a username."""

    authentication_classes = []
    permission_classes = [HasScope]
    required_scope = 'handoff'

    def post(self, request):
        username = request.data.get('username', '')
        user = get_user_model().objects.filter(username=username, is_active=True).first()
        if user is None:
            return Response({'error': 'No active account with that username.'}, status=404)
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
