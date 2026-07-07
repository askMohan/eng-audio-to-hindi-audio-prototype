from typing import Dict

from pipeline.provider_errors import UnknownProviderError
from speech_to_text.asr.faster_whisper import FasterWhisperASRProvider
from text_to_speech.providers.espeak import EspeakHindiTTSProvider
from translator.providers.ct2_opus_mt import CTranslate2OpusMTTranslationProvider
from translator.providers.opus_mt import OpusMTTranslationProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._asr = {
            "faster_whisper": FasterWhisperASRProvider,
        }
        self._translation = {
            "ct2_opus_mt": CTranslate2OpusMTTranslationProvider,
            "opus_mt": OpusMTTranslationProvider,
        }
        self._tts = {
            "espeak_hindi": EspeakHindiTTSProvider,
        }

    @classmethod
    def default(cls) -> "ProviderRegistry":
        return cls()

    def validate_provider_config(self, config: Dict[str, str]) -> None:
        self._validate_name(self._asr, config.get("asr", "faster_whisper"), "ASR")
        self._validate_name(
            self._translation,
            config.get("translation", "ct2_opus_mt"),
            "translation",
        )
        self._validate_name(self._tts, config.get("tts", "espeak_hindi"), "TTS")

    def get_asr(self, name: str):
        return self._build(self._asr, name, "ASR")

    def get_translation(self, name: str):
        return self._build(self._translation, name, "translation")

    def get_tts(self, name: str):
        return self._build(self._tts, name, "TTS")

    @staticmethod
    def _build(registry, name: str, provider_type: str):
        try:
            return registry[name]()
        except KeyError:
            raise UnknownProviderError("Unknown %s provider: %s" % (provider_type, name))

    @staticmethod
    def _validate_name(registry, name: str, provider_type: str) -> None:
        if name not in registry:
            raise UnknownProviderError("Unknown %s provider: %s" % (provider_type, name))
