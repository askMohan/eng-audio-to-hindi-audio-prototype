from django.db import models


class ProtectedTerm(models.Model):
    MODE_PRESERVE = "preserve"

    source = models.CharField(max_length=255, unique=True)
    target = models.CharField(max_length=255, blank=True)
    aliases = models.JSONField(default=list)
    mode = models.CharField(max_length=32, default=MODE_PRESERVE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "text_processing_protectedterm"
        indexes = [
            models.Index(fields=["is_active"], name="text_proces_is_acti_975f2b_idx"),
        ]

    def __str__(self) -> str:
        return self.source
