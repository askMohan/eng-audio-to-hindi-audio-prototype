import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.utils.text import slugify


@dataclass(frozen=True)
class ProcessingArtifactPaths:
    run_id: str
    raw_input_audio: Path
    audio_text: Path
    hindi_text: Path
    hindi_audio: Path
    events: Path


class ProcessingArtifactStore:
    RAW_INPUT_AUDIO = "audio/raw_input_audio"
    PROCESSED_AUDIO_TEXT = "processed_audio_text"
    PROCESSED_HINDI_TEXT = "processed_hindi_text"
    PROCESSED_HINDI_AUDIO = "processed_hindi_audio"
    EVENTS = "events"

    def __init__(self, root: Path = None) -> None:
        self.root = Path(root or settings.PROCESSING_DATA_ROOT)

    def ensure_directories(self) -> None:
        for relative_path in (
            self.RAW_INPUT_AUDIO,
            self.PROCESSED_AUDIO_TEXT,
            self.PROCESSED_HINDI_TEXT,
            self.PROCESSED_HINDI_AUDIO,
            self.EVENTS,
        ):
            (self.root / relative_path).mkdir(parents=True, exist_ok=True)

    def save_run(
        self,
        source_audio_path: Path,
        english_text: str,
        hindi_text: str,
        hindi_audio: bytes,
        events: Iterable[dict],
        run_id: str = None,
    ) -> ProcessingArtifactPaths:
        self.ensure_directories()
        source_audio_path = Path(source_audio_path)
        run_id = run_id or self._run_id(source_audio_path)
        audio_suffix = source_audio_path.suffix or ".audio"
        raw_audio_path = self.root / self.RAW_INPUT_AUDIO / ("%s%s" % (run_id, audio_suffix))
        audio_text_path = self.root / self.PROCESSED_AUDIO_TEXT / ("%s.txt" % run_id)
        hindi_text_path = self.root / self.PROCESSED_HINDI_TEXT / ("%s.txt" % run_id)
        hindi_audio_path = self.root / self.PROCESSED_HINDI_AUDIO / ("%s.wav" % run_id)
        events_path = self.root / self.EVENTS / ("%s.json" % run_id)

        shutil.copyfile(str(source_audio_path), str(raw_audio_path))
        audio_text_path.write_text(english_text, encoding="utf-8")
        hindi_text_path.write_text(hindi_text, encoding="utf-8")
        hindi_audio_path.write_bytes(hindi_audio)
        events_path.write_text(
            json.dumps(list(events), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ProcessingArtifactPaths(
            run_id=run_id,
            raw_input_audio=raw_audio_path,
            audio_text=audio_text_path,
            hindi_text=hindi_text_path,
            hindi_audio=hindi_audio_path,
            events=events_path,
        )

    def save_bytes(
        self,
        source_audio_name: str,
        source_audio: bytes,
        english_text: str,
        hindi_text: str,
        hindi_audio: bytes,
        events: Iterable[dict],
        run_id: str = None,
    ) -> ProcessingArtifactPaths:
        self.ensure_directories()
        source_name = Path(source_audio_name or "audio.pcm16")
        run_id = run_id or self._run_id(source_name)
        audio_suffix = source_name.suffix or ".audio"
        raw_audio_path = self.root / self.RAW_INPUT_AUDIO / ("%s%s" % (run_id, audio_suffix))
        audio_text_path = self.root / self.PROCESSED_AUDIO_TEXT / ("%s.txt" % run_id)
        hindi_text_path = self.root / self.PROCESSED_HINDI_TEXT / ("%s.txt" % run_id)
        hindi_audio_path = self.root / self.PROCESSED_HINDI_AUDIO / ("%s.wav" % run_id)
        events_path = self.root / self.EVENTS / ("%s.json" % run_id)

        raw_audio_path.write_bytes(source_audio)
        audio_text_path.write_text(english_text, encoding="utf-8")
        hindi_text_path.write_text(hindi_text, encoding="utf-8")
        hindi_audio_path.write_bytes(hindi_audio)
        events_path.write_text(
            json.dumps(list(events), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ProcessingArtifactPaths(
            run_id=run_id,
            raw_input_audio=raw_audio_path,
            audio_text=audio_text_path,
            hindi_text=hindi_text_path,
            hindi_audio=hindi_audio_path,
            events=events_path,
        )

    @staticmethod
    def _run_id(source_audio_path: Path) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        stem = slugify(source_audio_path.stem) or "audio"
        return "%s_%s" % (timestamp, stem)
