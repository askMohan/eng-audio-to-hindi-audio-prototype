import math
import struct
import wave
from io import BytesIO
from typing import Iterable


def pcm16le_to_float32_mono(data: bytes) -> "object":
    try:
        import numpy as np
    except ImportError as exc:
        from pipeline.provider_errors import MissingProviderDependency

        raise MissingProviderDependency(
            "Install model dependencies with `pip install -r requirements-models.txt` "
            "to use real ASR providers."
        ) from exc

    samples = np.frombuffer(data, dtype="<i2").astype(np.float32)
    return samples / 32768.0


def float_samples_to_pcm16(samples: Iterable[float]) -> bytes:
    output = bytearray()
    for sample in samples:
        clamped = max(-1.0, min(1.0, float(sample)))
        output.extend(struct.pack("<h", int(clamped * 32767)))
    return bytes(output)


def pcm16_to_wav_bytes(data: bytes, sample_rate: int, channels: int = 1) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(data)
    return buffer.getvalue()


def confidence_from_avg_logprob(avg_logprob) -> float:
    if avg_logprob is None:
        return 0.0
    try:
        return max(0.0, min(1.0, math.exp(float(avg_logprob))))
    except (TypeError, ValueError, OverflowError):
        return 0.0
