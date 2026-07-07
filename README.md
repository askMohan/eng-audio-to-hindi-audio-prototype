# Real-Time English to Hindi Voice Translation

This is a Django + Channels prototype for English to Hindi voice translation.

The browser records English speech from the microphone, sends audio frames to the backend over WebSocket, and receives generated Hindi speech audio back. The backend pipeline is:

```text
English audio -> ASR -> English text -> Hindi translation -> Hindi TTS audio
```

Current local model/runtime stack:

- ASR: `faster-whisper` with `tiny.en`
- Translation: CTranslate2 OPUS-MT English to Hindi
- TTS: local `espeak-ng` Hindi voice

Detailed architecture is documented in `TECHNICAL_DESIGN.md`.

## Requirements

Install eSpeak NG before setup:

```bash
brew install espeak-ng
```

## Setup

From the project root:

```bash
make setup
```

This creates `.venv`, installs Python requirements, runs migrations, installs model dependencies, and warms/downloads the required local models.

If `.venv` or `models/` is deleted, run the same command again:

```bash
make setup
```

## Run

Start the app:

```bash
make run
```

Open:

```text
http://127.0.0.1:8000/
```

Use the page to record English audio, stop recording, and listen to the Hindi output.

## Useful Commands

```bash
make check           # run Django system check
make warmup-models   # download/convert/load ASR, translation, and TTS providers
make repair-models   # force reinstall pinned model dependencies
make clean-models    # remove local converted model folder
```
