from django.contrib import admin

from sessions.models import TranslationSession


@admin.register(TranslationSession)
class TranslationSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "tone", "latency_profile", "status", "expires_at", "created_at")
    list_filter = ("status", "tone", "latency_profile")
    search_fields = ("id",)

