import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict

from django.conf import settings
from django.utils import timezone

from pipeline.provider_registry import ProviderRegistry
from sessions.models import TranslationSession


@dataclass(frozen=True)
class SessionCreateData:
    tone: str
    latency_profile: str
    provider_config: Dict[str, str]


class SessionService:
    def __init__(self, provider_registry: ProviderRegistry = None) -> None:
        self.provider_registry = provider_registry or ProviderRegistry.default()

    def create_session(self, data: SessionCreateData) -> TranslationSession:
        provider_config = data.provider_config or dict(settings.PROVIDER_CONFIG)
        self.provider_registry.validate_provider_config(provider_config)
        session_id = "sess_%s" % uuid.uuid4().hex
        expires_at = timezone.now() + timedelta(seconds=settings.SESSION_TTL_SECONDS)
        return TranslationSession.objects.create(
            id=session_id,
            tone=data.tone,
            latency_profile=data.latency_profile,
            provider_config=provider_config,
            expires_at=expires_at,
        )

    @staticmethod
    def is_active(session: TranslationSession) -> bool:
        return (
            session.status == TranslationSession.STATUS_ACTIVE
            and session.expires_at > timezone.now()
        )

    @staticmethod
    def close_session(session: TranslationSession, status: str = TranslationSession.STATUS_CLOSED) -> None:
        session.status = status
        session.save(update_fields=["status", "last_activity_at"])
