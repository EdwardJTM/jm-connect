import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from rest_framework_api_key.models import AbstractAPIKey

HANDOFF_LIFETIME = timedelta(seconds=60)


class SystemAPIKey(AbstractAPIKey):
    """A key one system uses to call this one. name says who the caller is."""

    scopes = models.JSONField(default=list, blank=True, help_text='What this key may do, for example ["handoff"].')
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta(AbstractAPIKey.Meta):
        verbose_name = 'system API key'
        verbose_name_plural = 'system API keys'


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class HandoffToken(models.Model):
    """A one-time sign-in link. Only the hash is stored, so the table cannot be used to sign in."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, user):
        cls.objects.filter(expires_at__lt=timezone.now()).delete()
        token = secrets.token_urlsafe(32)
        cls.objects.create(user=user, token_hash=_hash(token), expires_at=timezone.now() + HANDOFF_LIFETIME)
        return token

    @classmethod
    def redeem(cls, token):
        """Returns the user once. The conditional update stops two requests both using one token."""
        now = timezone.now()
        found = cls.objects.filter(token_hash=_hash(token), used_at__isnull=True, expires_at__gt=now)
        handoff = found.select_related('user').first()
        if handoff is None or not found.update(used_at=now):
            return None
        return handoff.user if handoff.user.is_active else None
