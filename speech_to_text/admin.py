from django.contrib import admin

from speech_to_text.models import ProtectedTerm


@admin.register(ProtectedTerm)
class ProtectedTermAdmin(admin.ModelAdmin):
    list_display = ("source", "target", "mode", "is_active", "updated_at")
    list_filter = ("is_active", "mode")
    search_fields = ("source", "target", "aliases")
