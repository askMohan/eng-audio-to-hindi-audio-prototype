import asyncio
import re
import warnings
from pathlib import Path
from typing import Dict

from django.conf import settings

from pipeline.contracts import SessionTextContext, TranslationInput, TranslationResult
from pipeline.provider_errors import MissingProviderDependency
from pipeline.runtime_env import configure_local_model_runtime


class CTranslate2OpusMTTranslationProvider:
    name = "ct2_opus_mt"

    _tokenizer = None
    _translator = None

    async def warm_up(self) -> None:
        await asyncio.to_thread(self._warm_up_sync)

    async def translate(self, data: TranslationInput) -> TranslationResult:
        return await asyncio.to_thread(self._translate_sync, data)

    def _translate_sync(self, data: TranslationInput) -> TranslationResult:
        tokenizer, translator = self._get_runtime()
        placeholder_map = self._compact_placeholders(data.text)
        source_text = placeholder_map["text"]
        source_tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(source_text))
        result = translator.translate_batch(
            [source_tokens],
            beam_size=settings.CT2_OPUS_MT_BEAM_SIZE,
            max_decoding_length=settings.CT2_OPUS_MT_MAX_DECODING_LENGTH,
        )[0]
        target_tokens = result.hypotheses[0]
        target_ids = tokenizer.convert_tokens_to_ids(target_tokens)
        text = tokenizer.decode(target_ids, skip_special_tokens=True)
        text = self._restore_compact_placeholders(text, placeholder_map["reverse"])
        return TranslationResult(text=text)

    def _warm_up_sync(self) -> None:
        self._translate_sync(
            TranslationInput(
                text="Hello.",
                tone="polite_conversational",
                protected_terms=[],
                context=SessionTextContext(),
            )
        )

    def _get_runtime(self):
        if CTranslate2OpusMTTranslationProvider._tokenizer is not None:
            return (
                CTranslate2OpusMTTranslationProvider._tokenizer,
                CTranslate2OpusMTTranslationProvider._translator,
            )
        configure_local_model_runtime()
        try:
            import ctranslate2
            from ctranslate2.converters import TransformersConverter
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise MissingProviderDependency(
                "Install CTranslate2 and transformers with `pip install -r requirements-models.txt`."
            ) from exc

        class CompatibleTransformersConverter(TransformersConverter):
            def load_model(self, model_class, model_name_or_path, **kwargs):
                kwargs.pop("dtype", None)
                return super().load_model(model_class, model_name_or_path, **kwargs)

        model_dir = Path(settings.CT2_OPUS_MT_MODEL_DIR)
        if not (model_dir / "model.bin").exists():
            model_dir.mkdir(parents=True, exist_ok=True)
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message="`torch_dtype` is deprecated! Use `dtype` instead!",
                    )
                    CompatibleTransformersConverter(settings.OPUS_MT_MODEL).convert(
                        str(model_dir),
                        quantization=settings.CT2_OPUS_MT_QUANTIZATION,
                        force=True,
                    )
            except ValueError as exc:
                if "torch.load" in str(exc) and "v2.6" in str(exc):
                    raise MissingProviderDependency(
                        "CTranslate2 OPUS-MT conversion is blocked by your installed Transformers "
                        "version requiring torch>=2.6. On this Python/macOS setup, install the "
                        "project's pinned model stack with "
                        "`.venv/bin/python -m pip install --force-reinstall -r requirements-models.txt`."
                    ) from exc
                raise

        tokenizer = AutoTokenizer.from_pretrained(settings.OPUS_MT_MODEL)
        translator = ctranslate2.Translator(
            str(model_dir),
            device=settings.CT2_OPUS_MT_DEVICE,
            compute_type=settings.CT2_OPUS_MT_COMPUTE_TYPE,
        )
        CTranslate2OpusMTTranslationProvider._tokenizer = tokenizer
        CTranslate2OpusMTTranslationProvider._translator = translator
        return tokenizer, translator

    @staticmethod
    def _compact_placeholders(text: str) -> Dict[str, object]:
        reverse = {}

        def replace(match):
            token = "TERM%s" % match.group(1)
            reverse[token] = match.group(0)
            return token

        compacted = re.sub(r"\{\{TERM_(\d+)\}\}", replace, text)
        return {"text": compacted, "reverse": reverse}

    @staticmethod
    def _restore_compact_placeholders(text: str, reverse: Dict[str, str]) -> str:
        restored = text
        for token, placeholder in reverse.items():
            restored = re.sub(r"\b%s\b" % re.escape(token), placeholder, restored)
            restored = restored.replace(token.lower(), placeholder)
        return restored

