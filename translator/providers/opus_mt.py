import asyncio
import re
from typing import Dict

from django.conf import settings

from pipeline.contracts import SessionTextContext, TranslationInput, TranslationResult
from pipeline.provider_errors import MissingProviderDependency
from pipeline.runtime_env import configure_local_model_runtime


class OpusMTTranslationProvider:
    name = "opus_mt"

    _tokenizer = None
    _model = None

    async def warm_up(self) -> None:
        await asyncio.to_thread(self._warm_up_sync)

    async def translate(self, data: TranslationInput) -> TranslationResult:
        return await asyncio.to_thread(self._translate_sync, data)

    def _translate_sync(self, data: TranslationInput) -> TranslationResult:
        tokenizer, model = self._get_model()
        placeholder_map = self._compact_placeholders(data.text)
        model_text = placeholder_map["text"]
        inputs = tokenizer(model_text, return_tensors="pt", truncation=True)
        device = getattr(model, "device", None)
        if device is not None:
            inputs = {key: value.to(device) for key, value in inputs.items()}
        try:
            import torch
        except ImportError:
            torch = None
        if torch is None:
            generated = model.generate(
                **inputs,
                max_new_tokens=settings.OPUS_MT_MAX_NEW_TOKENS,
                num_beams=settings.OPUS_MT_NUM_BEAMS,
            )
        else:
            with torch.inference_mode():
                generated = model.generate(
                    **inputs,
                    max_new_tokens=settings.OPUS_MT_MAX_NEW_TOKENS,
                    num_beams=settings.OPUS_MT_NUM_BEAMS,
                    do_sample=False,
                    use_cache=True,
                )
        text = tokenizer.decode(generated[0], skip_special_tokens=True)
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

    def _get_model(self):
        if OpusMTTranslationProvider._tokenizer is not None:
            return OpusMTTranslationProvider._tokenizer, OpusMTTranslationProvider._model
        configure_local_model_runtime()
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise MissingProviderDependency(
                "Install transformers and torch with `pip install -r requirements-models.txt`."
            ) from exc
        torch.set_num_threads(1)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass
        tokenizer = AutoTokenizer.from_pretrained(settings.OPUS_MT_MODEL)
        model = AutoModelForSeq2SeqLM.from_pretrained(
            settings.OPUS_MT_MODEL,
            use_safetensors=True,
        )
        device = settings.OPUS_MT_DEVICE
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        model.eval()
        OpusMTTranslationProvider._tokenizer = tokenizer
        OpusMTTranslationProvider._model = model
        return tokenizer, model

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
