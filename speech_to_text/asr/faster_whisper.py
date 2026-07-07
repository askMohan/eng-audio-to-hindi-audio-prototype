import asyncio
from typing import AsyncIterator, List

from django.conf import settings

from pipeline.contracts import ASREvent, ASRResult, ASRWord, AudioChunk, AudioFrame
from pipeline.provider_errors import MissingProviderDependency
from pipeline.runtime_env import configure_local_model_runtime
from speech_to_text.audio_utils import confidence_from_avg_logprob, pcm16le_to_float32_mono


class FasterWhisperASRProvider:
    name = "faster_whisper"
    supports_streaming = False

    _model = None

    def __init__(self) -> None:
        self.model_name = settings.FASTER_WHISPER_MODEL
        self.device = settings.FASTER_WHISPER_DEVICE
        self.compute_type = settings.FASTER_WHISPER_COMPUTE_TYPE
        self.beam_size = settings.FASTER_WHISPER_BEAM_SIZE

    async def transcribe_chunk(self, audio_chunk: AudioChunk) -> ASRResult:
        return await asyncio.to_thread(self._transcribe_sync, audio_chunk)

    async def transcribe_stream(self, frames: AsyncIterator[AudioFrame]) -> AsyncIterator[ASREvent]:
        buffered = []
        async for frame in frames:
            buffered.append(frame)
        if not buffered:
            return
        chunk = AudioChunk(
            chunk_id="stream",
            start_ms=buffered[0].timestamp_ms,
            end_ms=buffered[-1].timestamp_ms,
            frames=buffered,
            data=b"".join(frame.data for frame in buffered),
        )
        result = await self.transcribe_chunk(chunk)
        yield ASREvent(
            event_type="final",
            text=result.text,
            start_ms=result.start_ms,
            end_ms=result.end_ms,
            confidence=result.confidence,
        )

    def _transcribe_sync(self, audio_chunk: AudioChunk) -> ASRResult:
        model = self._get_model()
        waveform = pcm16le_to_float32_mono(audio_chunk.data)
        segments, _ = model.transcribe(
            waveform,
            language="en",
            task="transcribe",
            beam_size=self.beam_size,
            vad_filter=True,
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        segment_list = list(segments)
        text = " ".join(segment.text.strip() for segment in segment_list).strip()
        words: List[ASRWord] = []
        confidences = []
        for segment in segment_list:
            confidences.append(confidence_from_avg_logprob(getattr(segment, "avg_logprob", None)))
            for word in getattr(segment, "words", None) or []:
                words.append(
                    ASRWord(
                        text=word.word.strip(),
                        start_ms=audio_chunk.start_ms + int(word.start * 1000),
                        end_ms=audio_chunk.start_ms + int(word.end * 1000),
                        confidence=getattr(word, "probability", None),
                    )
                )
        confidence = None
        if confidences:
            confidence = sum(confidences) / len(confidences)
        return ASRResult(
            text=text,
            start_ms=audio_chunk.start_ms,
            end_ms=audio_chunk.end_ms,
            confidence=confidence,
            words=words,
        )

    def _get_model(self):
        if FasterWhisperASRProvider._model is not None:
            return FasterWhisperASRProvider._model
        configure_local_model_runtime()
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise MissingProviderDependency(
                "Install faster-whisper with `pip install -r requirements-models.txt`."
            ) from exc
        FasterWhisperASRProvider._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )
        return FasterWhisperASRProvider._model
