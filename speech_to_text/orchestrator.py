import asyncio
import time

from django.conf import settings

from observability.metrics import SegmentMetrics
from pipeline.contracts import ASRResult, AudioChunk
from pipeline.provider_errors import ProviderTimeout


class SpeechToTextOrchestrator:
    def __init__(self, provider) -> None:
        self.provider = provider

    async def transcribe(self, chunk: AudioChunk, metrics: SegmentMetrics) -> ASRResult:
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self.provider.transcribe_chunk(chunk),
                timeout=settings.ASR_TIMEOUT_MS / 1000,
            )
        except asyncio.TimeoutError as exc:
            raise ProviderTimeout(
                "ASR provider timed out after %s ms. Increase ASR_TIMEOUT_MS if this "
                "provider needs more time on your machine."
                % settings.ASR_TIMEOUT_MS
            ) from exc
        metrics.mark_ms("asrMs", started)
        return result
