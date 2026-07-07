import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import AsyncIterator

from django.conf import settings

from pipeline.contracts import TTSAudioFrame, TTSInput, TTSResult
from pipeline.provider_errors import MissingProviderDependency, ProviderError


class EspeakHindiTTSProvider:
    name = "espeak_hindi"
    supports_streaming = False

    def __init__(self) -> None:
        self.binary = self._find_binary()
        self.voice = settings.ESPEAK_HINDI_VOICE
        self.speed = settings.ESPEAK_HINDI_SPEED
        self.pitch = settings.ESPEAK_HINDI_PITCH

    async def synthesize(self, data: TTSInput) -> TTSResult:
        return await asyncio.to_thread(self._synthesize_sync, data)

    async def synthesize_stream(self, data: TTSInput) -> AsyncIterator[TTSAudioFrame]:
        result = await self.synthesize(data)
        for frame in result.frames:
            yield frame

    def _synthesize_sync(self, data: TTSInput) -> TTSResult:
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "speech.wav"
            command = [
                self.binary,
                "-v",
                self.voice,
                "-s",
                str(self.speed),
                "-p",
                str(self.pitch),
                "-w",
                str(wav_path),
                data.text,
            ]
            completed = subprocess.run(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if completed.returncode != 0:
                raise ProviderError(
                    "eSpeak Hindi synthesis failed: %s"
                    % completed.stderr.decode("utf-8", errors="ignore").strip()
                )
            return TTSResult(
                frames=[
                    TTSAudioFrame(
                        seq=1,
                        data=wav_path.read_bytes(),
                        format="wav",
                        sample_rate=22050,
                        is_final=True,
                    )
                ]
            )

    @staticmethod
    def _find_binary() -> str:
        binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if binary:
            return binary
        raise MissingProviderDependency(
            "Install eSpeak NG to use TTS_PROVIDER=espeak_hindi. "
            "On macOS: `brew install espeak-ng`."
        )
