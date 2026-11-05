from django.contrib import admin
from rest_framework_api_key.admin import APIKeyModelAdmin

from .models import SystemAPIKey


@admin.register(SystemAPIKey)
class SystemAPIKeyAdmin(APIKeyModelAdmin):
    list_display = [*APIKeyModelAdmin.list_display, 'scopes', 'last_used_at']
