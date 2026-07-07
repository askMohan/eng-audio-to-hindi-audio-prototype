from typing import Iterable

from pipeline.contracts import AudioFrame
from storage.artifacts import ProcessingArtifactPaths, ProcessingArtifactStore


class SessionArtifactRecorder:
    def __init__(self, store: ProcessingArtifactStore = None) -> None:
        self.store = store or ProcessingArtifactStore()

    def save(
        self,
        session_id: str,
        frames: Iterable[AudioFrame],
        events: Iterable[dict],
    ) -> ProcessingArtifactPaths:
        event_list = list(events)
        raw_audio = b"".join(frame.data for frame in sorted(frames, key=lambda item: item.seq))
        english_text = "\n".join(
            event.get("text", "") for event in event_list if event.get("type") == "asr.final"
        ).strip()
        hindi_text = "\n".join(
            event.get("translatedText", "")
            for event in event_list
            if event.get("type") == "translation.final"
        ).strip()
        hindi_audio = b"".join(
            event.get("data", "").encode("latin1")
            for event in event_list
            if event.get("type") == "tts.audio"
        )
        return self.store.save_bytes(
            source_audio_name="%s.pcm16" % session_id,
            source_audio=raw_audio,
            english_text=english_text,
            hindi_text=hindi_text,
            hindi_audio=hindi_audio,
            events=event_list,
            run_id=session_id,
        )
