import asyncio
import time
from typing import List

from django.conf import settings

from observability.metrics import SegmentMetrics
from pipeline.contracts import TTSAudioFrame, TTSInput
from pipeline.provider_errors import ProviderTimeout


class TTSOrchestrator:
    def __init__(self, provider) -> None:
        self.provider = provider

    async def synthesize(self, text: str, metrics: SegmentMetrics) -> List[TTSAudioFrame]:
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self.provider.synthesize(TTSInput(text=text)),
                timeout=settings.TTS_TIMEOUT_MS / 1000,
            )
        except asyncio.TimeoutError as exc:
            raise ProviderTimeout(
                "TTS provider timed out after %s ms. Increase TTS_TIMEOUT_MS if this "
                "provider needs more time on your machine."
                % settings.TTS_TIMEOUT_MS
            ) from exc
        metrics.mark_ms("ttsFirstByteMs", started)
        return result.frames
