from django.utils import timezone
from rest_framework_api_key.permissions import BaseHasAPIKey

from .models import SystemAPIKey


class HasScope(BaseHasAPIKey):
    """Needs a valid key that lists the view's required_scope."""

    model = SystemAPIKey

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        key = self.model.objects.get_from_key(self.get_key(request))
        if view.required_scope not in key.scopes:
            return False
        self.model.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return True
