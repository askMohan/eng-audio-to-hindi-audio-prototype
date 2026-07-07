from typing import Optional


class PlaybackInterruptionController:
    def __init__(self) -> None:
        self.active_tts_segment_id: Optional[str] = None

    def playback_started(self, tts_segment_id: str) -> None:
        self.active_tts_segment_id = tts_segment_id

    def playback_stopped(self, tts_segment_id: str) -> None:
        if self.active_tts_segment_id == tts_segment_id:
            self.active_tts_segment_id = None

    def should_interrupt(self, has_user_speech: bool) -> bool:
        return bool(self.active_tts_segment_id and has_user_speech)
