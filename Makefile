SHELL := /bin/zsh

PYTHON ?= python3
VENV ?= .venv
HOST ?= 127.0.0.1
PORT ?= 8000

VENV_PYTHON := $(VENV)/bin/python
PIP := $(VENV_PYTHON) -m pip
UVICORN := $(VENV_PYTHON) -m uvicorn

.PHONY: help setup venv install install-models repair-models migrate check check-runtime warmup-models run clean-models

help:
	@echo "Available targets:"
	@echo "  make setup          Create venv, install deps, migrate DB, check runtime, warm models"
	@echo "  make install        Install Django/backend requirements"
	@echo "  make install-models Install ASR/translation model requirements"
	@echo "  make repair-models  Force reinstall pinned model stack"
	@echo "  make migrate        Run Django migrations"
	@echo "  make warmup-models  Download/convert/load ASR, translation, and TTS providers"
	@echo "  make check          Run Django system checks"
	@echo "  make run            Start local ASGI server at http://$(HOST):$(PORT)/"
	@echo "  make clean-models   Remove locally converted/downloaded project model folder"

setup: install-models migrate check-runtime warmup-models check

venv: $(VENV_PYTHON)

$(VENV_PYTHON):
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel

install: venv
	$(PIP) install -r requirements.txt

install-models: install
	$(PIP) install -r requirements-models.txt

repair-models: venv
	$(PIP) install --force-reinstall -r requirements-models.txt

migrate: install
	$(VENV_PYTHON) manage.py migrate --fake-initial

check: install
	$(VENV_PYTHON) manage.py check

check-runtime:
	@command -v espeak-ng >/dev/null 2>&1 || command -v espeak >/dev/null 2>&1 || (echo "Missing eSpeak runtime. On macOS run: brew install espeak-ng" && exit 1)

warmup-models: install-models migrate check-runtime
	@mkdir -p models
	$(VENV_PYTHON) -c "import os, django, asyncio; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from django.conf import settings; from pipeline.provider_registry import ProviderRegistry; registry = ProviderRegistry.default(); provider = registry.get_translation(settings.PROVIDER_CONFIG['translation']); asyncio.run(provider.warm_up()); print('Translation model ready:', settings.PROVIDER_CONFIG['translation'])"
	$(VENV_PYTHON) -c "import os, django, asyncio; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from django.conf import settings; from pipeline.provider_registry import ProviderRegistry; from pipeline.contracts import AudioChunk; registry = ProviderRegistry.default(); provider = registry.get_asr(settings.PROVIDER_CONFIG['asr']); chunk = AudioChunk(chunk_id='warmup', start_ms=0, end_ms=1000, frames=[], data=b'\x00\x00' * 16000); asyncio.run(provider.transcribe_chunk(chunk)); print('ASR model ready:', settings.PROVIDER_CONFIG['asr'])"
	$(VENV_PYTHON) -c "import os, django, asyncio; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from django.conf import settings; from pipeline.provider_registry import ProviderRegistry; from pipeline.contracts import TTSInput; registry = ProviderRegistry.default(); provider = registry.get_tts(settings.PROVIDER_CONFIG['tts']); asyncio.run(provider.synthesize(TTSInput(text='नमस्ते'))); print('TTS runtime ready:', settings.PROVIDER_CONFIG['tts'])"

run: install
	$(UVICORN) config.asgi:application --host $(HOST) --port $(PORT)

clean-models:
	rm -rf models
