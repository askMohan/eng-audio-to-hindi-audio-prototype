from django.conf import settings
from rest_framework import serializers

from sessions.services import SessionCreateData


class SessionCreateSerializer(serializers.Serializer):
    tone = serializers.ChoiceField(
        choices=("formal", "casual", "business", "polite_conversational"),
        default="polite_conversational",
        required=False,
    )
    latencyProfile = serializers.ChoiceField(
        choices=("balanced", "lowest_latency", "highest_quality"),
        default="balanced",
        required=False,
    )
    audio = serializers.DictField(required=False)
    providers = serializers.DictField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        disallowed = {"sourceLanguage", "targetLanguage", "glossary"}
        submitted = set(getattr(self, "initial_data", {}).keys())
        unexpected = sorted(submitted.intersection(disallowed))
        if unexpected:
            raise serializers.ValidationError(
                "Unsupported field(s): %s. This service is fixed English to Hindi." % ", ".join(unexpected)
            )
        return attrs

    def to_service_data(self) -> SessionCreateData:
        providers = self.validated_data.get("providers") or dict(settings.PROVIDER_CONFIG)
        return SessionCreateData(
            tone=self.validated_data.get("tone", "polite_conversational"),
            latency_profile=self.validated_data.get("latencyProfile", "balanced"),
            provider_config=providers,
        )


class SessionResponseSerializer(serializers.Serializer):
    sessionId = serializers.CharField()
    streamUrl = serializers.CharField()
    expiresAt = serializers.DateTimeField()

