import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class SegmentMetrics:
    segment_id: str
    started_at: float = field(default_factory=time.monotonic)
    values: Dict[str, int] = field(default_factory=dict)

    def mark_ms(self, key: str, started_at: float) -> None:
        self.values[key] = int((time.monotonic() - started_at) * 1000)

    def as_event(self) -> Dict:
        return {
            "type": "metrics.latency",
            "segmentId": self.segment_id,
            "vadMs": self.values.get("vadMs", 0),
            "asrMs": self.values.get("asrMs", 0),
            "translationMs": self.values.get("translationMs", 0),
            "ttsFirstByteMs": self.values.get("ttsFirstByteMs", 0),
            "totalFirstAudioMs": int((time.monotonic() - self.started_at) * 1000),
        }

