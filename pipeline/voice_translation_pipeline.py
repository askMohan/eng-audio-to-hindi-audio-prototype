import asyncio
import time
from typing import AsyncIterator, Dict, Iterable, List

from django.conf import settings

from speech_to_text.codecs import AudioCodecService, UnsupportedAudioFormat
from speech_to_text.chunking import VADChunker
from speech_to_text.orchestrator import SpeechToTextOrchestrator
from speech_to_text.transcript_stability import TranscriptStabilityChecker
from observability.metrics import SegmentMetrics
from pipeline.errors import UnsupportedAudioFormatError
from pipeline.contracts import AudioFrame, SessionTextContext
from pipeline.provider_registry import ProviderRegistry
from text_to_speech.orchestrator import TTSOrchestrator
from translator.orchestrator import TranslationOrchestrator


class VoiceTranslationPipeline:
    def __init__(self, provider_config: Dict[str, str], tone: str) -> None:
        registry = ProviderRegistry.default()
        self.tone = tone
        self.codec = AudioCodecService()
        self.chunker = VADChunker()
        self.speech_to_text = SpeechToTextOrchestrator(
            registry.get_asr(provider_config.get("asr", "faster_whisper"))
        )
        self.transcript_stability = TranscriptStabilityChecker()
        self.translation = TranslationOrchestrator(
            registry.get_translation(provider_config.get("translation", "ct2_opus_mt"))
        )
        self.tts = TTSOrchestrator(registry.get_tts(provider_config.get("tts", "espeak_hindi")))
        self.context = SessionTextContext()

    async def warm_up(self) -> None:
        warm_up = getattr(self.translation.provider, "warm_up", None)
        if warm_up is not None:
            await asyncio.wait_for(
                warm_up(),
                timeout=settings.TRANSLATION_WARMUP_TIMEOUT_MS / 1000,
            )

    async def process_frames(self, frames: Iterable[AudioFrame]) -> List[Dict]:
        events = []
        async for event in self.iter_events(frames):
            events.append(event)
        return events

    async def iter_events(self, frames: Iterable[AudioFrame]) -> AsyncIterator[Dict]:
        decoded_frames = []
        for frame in frames:
            try:
                decoded = self.codec.decode_to_pcm(frame.data, frame.format)
            except UnsupportedAudioFormat:
                raise UnsupportedAudioFormatError("Unsupported format: %s" % frame.format)
            decoded_frames.append(
                AudioFrame(
                    seq=frame.seq,
                    timestamp_ms=frame.timestamp_ms,
                    format="pcm16",
                    sample_rate=frame.sample_rate,
                    channels=frame.channels,
                    data=decoded,
                )
            )

        vad_started = time.monotonic()
        chunks = self.chunker.chunk(decoded_frames)
        for chunk in chunks:
            metrics = SegmentMetrics(segment_id=chunk.chunk_id)
            metrics.mark_ms("vadMs", vad_started)
            yield self._stage_event(chunk.chunk_id, "asr_started")
            asr_result = await self.speech_to_text.transcribe(chunk, metrics)
            yield {
                "type": "asr.final",
                "segmentId": chunk.chunk_id,
                "text": asr_result.text,
                "confidence": asr_result.confidence,
                "startMs": asr_result.start_ms,
                "endMs": asr_result.end_ms,
            }
            if not self.transcript_stability.is_translation_ready(asr_result):
                yield {
                    "type": "segment.skipped",
                    "segmentId": chunk.chunk_id,
                    "reason": self._skip_reason(asr_result),
                    "text": asr_result.text,
                }
                yield metrics.as_event()
                continue
            yield self._stage_event(chunk.chunk_id, "translation_started")
            translation = await self.translation.translate(
                asr_result.text,
                self.tone,
                self.context,
                metrics,
            )
            self.context.recent_english.append(asr_result.text)
            self.context.recent_hindi.append(translation.text)
            self.context.recent_english = self.context.recent_english[-10:]
            self.context.recent_hindi = self.context.recent_hindi[-10:]
            yield {
                "type": "translation.final",
                "segmentId": chunk.chunk_id,
                "sourceText": asr_result.text,
                "translatedText": translation.text,
                "tone": self.tone,
            }
            yield self._stage_event(chunk.chunk_id, "tts_started")
            tts_frames = await self.tts.synthesize(translation.text, metrics)
            tts_segment_id = "tts_%s" % chunk.chunk_id
            for frame in tts_frames:
                yield {
                    "type": "tts.audio",
                    "ttsSegmentId": tts_segment_id,
                    "segmentId": chunk.chunk_id,
                    "seq": frame.seq,
                    "format": frame.format,
                    "sampleRate": frame.sample_rate,
                    "isFinal": frame.is_final,
                    "data": frame.data.decode("latin1"),
                }
            yield metrics.as_event()

    @staticmethod
    def _stage_event(segment_id: str, stage: str) -> Dict:
        return {
            "type": "pipeline.stage",
            "segmentId": segment_id,
            "stage": stage,
        }

    @staticmethod
    def _skip_reason(asr_result) -> str:
        if not asr_result.text.strip():
            return "empty_transcript"
        if asr_result.confidence is not None and asr_result.confidence < 0.55:
            return "low_confidence_transcript"
        return "transcript_not_ready"
