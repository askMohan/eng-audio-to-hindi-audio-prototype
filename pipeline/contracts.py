from dataclasses import dataclass, field
from typing import AsyncIterator, List, Optional, Protocol


@dataclass(frozen=True)
class AudioFrame:
    seq: int
    timestamp_ms: int
    format: str
    sample_rate: int
    channels: int
    data: bytes


@dataclass(frozen=True)
class AudioChunk:
    chunk_id: str
    start_ms: int
    end_ms: int
    frames: List[AudioFrame]
    data: bytes


@dataclass(frozen=True)
class ASRWord:
    text: str
    start_ms: int
    end_ms: int
    confidence: Optional[float] = None


@dataclass(frozen=True)
class ASRAlternative:
    text: str
    confidence: Optional[float] = None


@dataclass(frozen=True)
class ASRResult:
    text: str
    start_ms: int
    end_ms: int
    confidence: Optional[float] = None
    words: List[ASRWord] = field(default_factory=list)
    alternatives: List[ASRAlternative] = field(default_factory=list)


@dataclass(frozen=True)
class ASREvent:
    event_type: str
    text: str
    start_ms: int
    end_ms: int
    confidence: Optional[float] = None


@dataclass(frozen=True)
class ProtectedTermMatch:
    placeholder: str
    source: str
    target: str
    start: int
    end: int


@dataclass
class SessionTextContext:
    recent_english: List[str] = field(default_factory=list)
    recent_hindi: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class TranslationInput:
    text: str
    tone: str
    protected_terms: List[ProtectedTermMatch]
    context: SessionTextContext


@dataclass(frozen=True)
class TranslationResult:
    text: str
    preserved_terms: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class TTSInput:
    text: str
    voice: str = "default_hindi"
    output_format: str = "pcm16"
    sample_rate: int = 24000


@dataclass(frozen=True)
class TTSAudioFrame:
    seq: int
    data: bytes
    format: str
    sample_rate: int
    is_final: bool = False


@dataclass(frozen=True)
class TTSResult:
    frames: List[TTSAudioFrame]


class ASRProvider(Protocol):
    name: str
    supports_streaming: bool

    async def transcribe_chunk(self, audio_chunk: AudioChunk) -> ASRResult:
        ...

    async def transcribe_stream(self, frames: AsyncIterator[AudioFrame]) -> AsyncIterator[ASREvent]:
        ...


class TranslationProvider(Protocol):
    name: str

    async def translate(self, data: TranslationInput) -> TranslationResult:
        ...


class TTSProvider(Protocol):
    name: str
    supports_streaming: bool

    async def synthesize(self, data: TTSInput) -> TTSResult:
        ...

    async def synthesize_stream(self, data: TTSInput) -> AsyncIterator[TTSAudioFrame]:
        ...
