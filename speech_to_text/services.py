import base64
from typing import Dict

from django.conf import settings

from pipeline.contracts import AudioFrame


class AudioFrameParser:
    def parse(self, message: Dict) -> AudioFrame:
        raw = base64.b64decode(message.get("data", ""), validate=True)
        if len(raw) > settings.MAX_AUDIO_FRAME_BYTES:
            raise ValueError("Audio frame exceeds max size")
        return AudioFrame(
            seq=int(message["seq"]),
            timestamp_ms=int(message.get("timestampMs", 0)),
            format=message.get("format", "pcm16"),
            sample_rate=int(message.get("sampleRate", 16000)),
            channels=int(message.get("channels", 1)),
            data=raw,
        )
