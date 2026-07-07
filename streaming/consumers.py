import base64
import asyncio
from typing import List

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from speech_to_text.services import AudioFrameParser
from pipeline.contracts import AudioFrame
from pipeline.errors import PipelineError
from pipeline.provider_errors import ProviderError
from pipeline.voice_translation_pipeline import VoiceTranslationPipeline
from sessions.models import TranslationSession
from sessions.services import SessionService
from storage.session_artifacts import SessionArtifactRecorder
from streaming.playback_interruptions import PlaybackInterruptionController


class VoiceTranslationStreamConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.session = await self._get_active_session(self.session_id)
        if self.session is None:
            await self.close(code=4404)
            return
        self.parser = AudioFrameParser()
        self.frames: List[AudioFrame] = []
        self.invalid_messages = 0
        self.cancelled = False
        self.last_seq = -1
        self.interruptions = PlaybackInterruptionController()
        self.artifact_recorder = SessionArtifactRecorder()
        self.pipeline = VoiceTranslationPipeline(
            provider_config=self.session.provider_config,
            tone=self.session.tone,
        )
        await self.accept()
        await self.send_json({"type": "pipeline.stage", "stage": "translation_model_loading"})
        try:
            await self.pipeline.warm_up()
        except asyncio.TimeoutError:
            await self._error(
                "TRANSLATION_MODEL_WARMUP_TIMEOUT",
                "Translation model warm-up timed out. Increase TRANSLATION_WARMUP_TIMEOUT_MS or use a faster translation runtime.",
                recoverable=False,
            )
            await self.close(code=4500)
            return
        except ProviderError as exc:
            await self._error(exc.code, str(exc), exc.recoverable)
            await self.close(code=4500)
            return
        except Exception as exc:
            await self._error("MODEL_WARMUP_FAILED", str(exc), recoverable=False)
            await self.close(code=4500)
            return
        await self.send_json({"type": "session.ready", "sessionId": self.session_id})

    async def disconnect(self, close_code):
        if hasattr(self, "session"):
            await self._close_session(self.session_id)

    async def receive_json(self, content, **kwargs):
        try:
            message_type = content.get("type")
            handler = self._client_message_handlers().get(message_type)
            if handler is None:
                await self._invalid("INVALID_MESSAGE", "Unknown message type")
                return
            result = handler(content)
            if asyncio.iscoroutine(result):
                await result
        except PipelineError as exc:
            await self._error(exc.code, str(exc), exc.recoverable)
        except ProviderError as exc:
            await self._error(exc.code, str(exc), exc.recoverable)
        except Exception as exc:
            await self._invalid("INVALID_MESSAGE", str(exc))

    def _client_message_handlers(self):
        return {
            "audio.frame": self._handle_audio_frame,
            "audio.end": self._handle_audio_end,
            "session.cancel": self._handle_session_cancel,
            "playback.started": self._handle_playback_started,
            "playback.stopped": self._handle_playback_stopped,
        }

    def _handle_playback_started(self, content):
        self.interruptions.playback_started(content["ttsSegmentId"])

    def _handle_playback_stopped(self, content):
        self.interruptions.playback_stopped(content["ttsSegmentId"])

    async def _handle_audio_frame(self, content):
        if self.cancelled:
            return
        frame = self.parser.parse(content)
        if frame.seq <= self.last_seq:
            await self._invalid("INVALID_MESSAGE", "Audio frame sequence must increase")
            return
        self.last_seq = frame.seq
        self.frames.append(frame)
        if self.interruptions.should_interrupt(has_user_speech=True):
            await self.send_json(
                {
                    "type": "interruption.detected",
                    "activeTtsSegmentId": self.interruptions.active_tts_segment_id,
                    "action": "cancel_tts_and_clear_queue",
                }
            )

    async def _handle_audio_end(self, content=None):
        if self.cancelled:
            return
        frames = list(self.frames)
        self.frames = []
        events = []
        async for event in self.pipeline.iter_events(frames):
            if self.cancelled:
                break
            events.append(event)
            await self._send_event(event)
        if not self.cancelled:
            await self._save_artifacts(frames, events)

    async def _handle_session_cancel(self, content=None):
        self.cancelled = True
        self.frames = []
        await self.send_json({"type": "session.cancelled"})
        await self.close(code=4401)

    async def _send_event(self, event):
        if self.cancelled:
            return
        if event["type"] == "tts.audio":
            event = dict(event)
            if isinstance(event["data"], str):
                event["data"] = base64.b64encode(event["data"].encode("latin1")).decode("ascii")
        await self.send_json(event)

    async def _save_artifacts(self, frames, events):
        await sync_to_async(self.artifact_recorder.save, thread_sensitive=False)(
            self.session_id,
            frames,
            events,
        )

    async def _invalid(self, code: str, message: str):
        self.invalid_messages += 1
        await self._error(code, message, recoverable=True)
        if self.invalid_messages >= settings.MAX_INVALID_MESSAGES:
            await self.close(code=4400)

    async def _error(self, code: str, message: str, recoverable: bool):
        await self.send_json(
            {
                "type": "error",
                "code": code,
                "message": message,
                "recoverable": recoverable,
            }
        )

    @database_sync_to_async
    def _get_active_session(self, session_id: str):
        try:
            session = TranslationSession.objects.get(id=session_id)
        except TranslationSession.DoesNotExist:
            return None
        if not SessionService.is_active(session):
            return None
        return session

    @database_sync_to_async
    def _close_session(self, session_id: str) -> None:
        try:
            session = TranslationSession.objects.get(id=session_id)
        except TranslationSession.DoesNotExist:
            return
        if session.status == TranslationSession.STATUS_ACTIVE:
            SessionService.close_session(session)
