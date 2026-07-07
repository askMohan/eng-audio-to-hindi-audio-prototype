import itertools
import uuid
from typing import Iterable, List

from pipeline.contracts import AudioChunk, AudioFrame


class VADChunker:
    def __init__(
        self,
        min_speech_ms: int = 200,
        max_chunk_ms: int = 4000,
    ) -> None:
        self.min_speech_ms = min_speech_ms
        self.max_chunk_ms = max_chunk_ms

    def chunk(self, frames: Iterable[AudioFrame]) -> List[AudioChunk]:
        ordered = sorted(frames, key=lambda frame: frame.seq)
        voiced = [frame for frame in ordered if self._is_voiced(frame)]
        if not voiced:
            return []
        grouped = []
        for _, group in itertools.groupby(
            voiced,
            key=lambda frame: int(frame.timestamp_ms / self.max_chunk_ms),
        ):
            group_frames = list(group)
            if not group_frames:
                continue
            start_ms = group_frames[0].timestamp_ms
            end_ms = max(frame.timestamp_ms for frame in group_frames) + 20
            data = b"".join(frame.data for frame in group_frames)
            grouped.append(
                AudioChunk(
                    chunk_id="seg_%s" % uuid.uuid4().hex[:12],
                    start_ms=start_ms,
                    end_ms=end_ms,
                    frames=group_frames,
                    data=data,
                )
            )
        return grouped

    @staticmethod
    def _is_voiced(frame: AudioFrame) -> bool:
        if frame.data.startswith(b"TEXT:"):
            return True
        return any(byte not in (0, 128) for byte in frame.data)
