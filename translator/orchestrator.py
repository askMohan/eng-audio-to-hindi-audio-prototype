import asyncio
import time

from asgiref.sync import sync_to_async
from django.conf import settings

from observability.metrics import SegmentMetrics
from pipeline.contracts import SessionTextContext, TranslationInput, TranslationResult
from pipeline.provider_errors import ProviderTimeout
from speech_to_text.normalization import TextNormalizer
from speech_to_text.preprocessing import TextPreprocessor
from speech_to_text.protected_terms import ProtectedTermService


class TranslationOrchestrator:
    def __init__(self, provider) -> None:
        self.provider = provider
        self.preprocessor = TextPreprocessor()
        self.normalizer = TextNormalizer()
        self.protected_terms = ProtectedTermService()

    async def translate(
        self,
        text: str,
        tone: str,
        context: SessionTextContext,
        metrics: SegmentMetrics,
    ) -> TranslationResult:
        started = time.monotonic()
        cleaned = self.preprocessor.clean(text)
        normalized = self.normalizer.normalize_for_hindi(cleaned)
        protected = await sync_to_async(self.protected_terms.protect)(normalized)
        translation_input = TranslationInput(
            text=protected.text,
            tone=tone,
            protected_terms=protected.matches,
            context=context,
        )
        try:
            result = await asyncio.wait_for(
                self.provider.translate(translation_input),
                timeout=settings.TRANSLATION_TIMEOUT_MS / 1000,
            )
        except asyncio.TimeoutError as exc:
            raise ProviderTimeout(
                "Translation provider timed out after %s ms. Increase TRANSLATION_TIMEOUT_MS "
                "if this provider needs more time on your machine."
                % settings.TRANSLATION_TIMEOUT_MS
            ) from exc
        restored = self.protected_terms.restore(result.text, protected.matches)
        metrics.mark_ms("translationMs", started)
        return TranslationResult(
            text=restored,
            preserved_terms=[match.target for match in protected.matches],
            warnings=result.warnings,
        )
