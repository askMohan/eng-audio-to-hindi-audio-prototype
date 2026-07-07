from django.urls import re_path

from streaming.consumers import VoiceTranslationStreamConsumer


websocket_urlpatterns = [
    re_path(
        r"^ws/sessions/(?P<session_id>[^/]+)/stream/$",
        VoiceTranslationStreamConsumer.as_asgi(),
    ),
]
