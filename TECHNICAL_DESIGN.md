# Technical Design: English to Hindi Voice Translation Backend

## Purpose

This project is a Django based voice-to-voice translation prototype. A user speaks in English through the browser, the backend converts the audio to English text, translates that text into Hindi, converts the Hindi text into speech, and sends the generated Hindi audio back to the browser.

The design is split by business responsibility:

- `speech_to_text/` owns audio parsing, chunking, ASR, transcript cleanup, and protected term handling.
- `translator/` owns English to Hindi translation.
- `text_to_speech/` owns Hindi speech generation.
- `streaming/` owns the WebSocket connection and live session messages.
- `sessions/` owns session creation, validation, expiry, and lifecycle.
- `pipeline/` coordinates the complete ASR to translation to TTS flow.
- `storage/` saves raw audio, intermediate text, final Hindi text, audio output, and event traces.
- `observability/` records per-stage latency metrics.

The current implementation is fixed to English input and Hindi output. There is no generic multi-language routing because the requirement is specifically English to Hindi.

## High Level Architecture

```text
Browser microphone
  -> Django Channels WebSocket
  -> Audio frame parser
  -> PCM decoder
  -> VAD-style chunker
  -> faster-whisper ASR
  -> English transcript cleanup
  -> protected term replacement
  -> CTranslate2 OPUS-MT English to Hindi translation
  -> protected term restore
  -> eSpeak Hindi TTS
  -> WebSocket TTS audio event
  -> browser playback
```

The browser streams audio frames while the user records. When the user stops recording, the backend processes the collected frames as one or more speech chunks. This is not yet token-by-token simultaneous interpretation. That choice is deliberate for the prototype because Hindi sentence order can depend on the full English phrase. Translating unstable partial English too early can produce awkward or incorrect Hindi.

## Backend Entry Points

### HTTP Session API

The frontend first calls:

```text
POST /api/sessions/
```

Code path:

```text
config/urls.py
  -> sessions.views.CreateSessionView.post()
  -> sessions.serializers.SessionCreateSerializer
  -> sessions.services.SessionService.create_session()
  -> sessions.models.TranslationSession
```

The session stores the selected tone, provider config, expiry time, and active/closed status. The response contains a WebSocket URL:

```text
ws://host/ws/sessions/<session_id>/stream/
```

The session is useful because the WebSocket is long-lived and needs a durable identity. It also gives us a place to validate provider config before streaming begins and to close or expire abandoned work.

### Why WebSocket Instead Of REST

The actual audio pipeline uses WebSocket instead of plain REST because this is an interactive streaming problem, not a simple request-response problem.

With REST, the browser would have to upload an entire audio file, wait for the server to finish ASR, translation, and TTS, and then download the final result. That works for batch processing, but it is a poor fit for live voice because the server also needs to send progress events, partial status, interruption events, latency metrics, and TTS audio back while the session is still active.

WebSocket gives us one long-lived two-way connection:

```text
Browser -> Server:
  audio.frame
  audio.end
  session.cancel
  playback.started
  playback.stopped

Server -> Browser:
  session.ready
  pipeline.stage
  asr.final
  translation.final
  tts.audio
  metrics.latency
  interruption.detected
  error
```

This is useful for four reasons:

1. Low overhead for many small audio frames.
   Audio is sent in small chunks. Sending each chunk as a separate REST request would add repeated HTTP headers, request setup cost, and more backend routing overhead.

2. Server can push events immediately.
   The server does not need to wait for the client to poll for status. As soon as ASR finishes, translation finishes, or TTS audio is ready, the backend can emit an event.

3. Interruption handling needs bidirectional state.
   The frontend tells the backend when Hindi TTS playback starts or stops. If the user speaks while playback is active, the backend can emit `interruption.detected` and the frontend can stop queued audio.

4. Session state stays coherent.
   A voice translation run has ordered audio frames, cancellation, playback state, model warm-up, and final artifact saving. Keeping these messages inside one WebSocket session is simpler and safer than spreading them across many independent REST calls.

REST is still used where it fits naturally: creating the session with `POST /api/sessions/`. After that, WebSocket owns the live stream.

### WebSocket Stream API

The WebSocket route is defined in:

```text
streaming/routing.py
```

It maps to:

```text
streaming.consumers.VoiceTranslationStreamConsumer
```

On connect, the consumer:

1. Reads the `session_id` from the URL.
2. Verifies the session is active.
3. Creates a `VoiceTranslationPipeline`.
4. Warms up the translation model.
5. Emits `session.ready`.

Client message handling uses an event-to-handler map:

```python
{
    "audio.frame": _handle_audio_frame,
    "audio.end": _handle_audio_end,
    "session.cancel": _handle_session_cancel,
    "playback.started": _handle_playback_started,
    "playback.stopped": _handle_playback_stopped,
}
```

This keeps the consumer maintainable. New WebSocket message types can be added by adding one handler and one map entry, instead of growing a large `if/else` block.

## Processing Flow

### 1. Audio Frame Intake

The browser sends `audio.frame` messages containing base64 encoded PCM audio.

Backend path:

```text
VoiceTranslationStreamConsumer.receive_json()
  -> VoiceTranslationStreamConsumer._handle_audio_frame()
  -> speech_to_text.services.AudioFrameParser.parse()
```

The parser validates sequence number, timestamp, format, sample rate, channel count, and encoded audio payload. Valid frames are kept in memory for the active session.

### 2. Processing Trigger

When the browser sends:

```json
{ "type": "audio.end" }
```

the backend starts the pipeline:

```text
VoiceTranslationStreamConsumer._handle_audio_end()
  -> pipeline.voice_translation_pipeline.VoiceTranslationPipeline.iter_events()
```

The pipeline yields events as each stage completes, and the WebSocket consumer sends those events to the frontend.

### 3. Decode and Chunk Audio

Code path:

```text
speech_to_text.codecs.AudioCodecService.decode_to_pcm()
  -> speech_to_text.chunking.VADChunker.chunk()
```

The codec layer normalizes incoming audio to PCM. The chunker groups audio into speech-sized chunks. This avoids sending every tiny frame directly to ASR and helps prevent incomplete phrases from being translated too early.

### 4. Speech to Text

Code path:

```text
speech_to_text.orchestrator.SpeechToTextOrchestrator.transcribe()
  -> speech_to_text.asr.faster_whisper.FasterWhisperASRProvider.transcribe_chunk()
  -> faster_whisper.WhisperModel.transcribe()
```

Actual model:

```text
faster-whisper with model tiny.en
```

Model settings are read from `config/settings.py`:

```python
FASTER_WHISPER_MODEL = "tiny.en"
FASTER_WHISPER_DEVICE = "cpu"
FASTER_WHISPER_COMPUTE_TYPE = "int8"
FASTER_WHISPER_BEAM_SIZE = 5
```

The ASR provider returns English text, timestamps, confidence, and optional word timestamps. The pipeline emits `asr.final`. If the ASR output is empty or low confidence, it emits `segment.skipped` and does not run translation or TTS for that chunk.

### 5. English Text Cleanup

Code path:

```text
translator.orchestrator.TranslationOrchestrator.translate()
  -> speech_to_text.preprocessing.TextPreprocessor.clean()
  -> speech_to_text.normalization.TextNormalizer.normalize_for_hindi()
```

The cleanup stage removes obvious fillers like `uh`, `uhh`, `um`, `umm`, `erm`, and `ah`.

It handles phrases like `you know` conservatively. The code removes it only when it looks like a discourse filler, for example when it appears at the start with a comma-like pause or between punctuation. It does not blindly remove every occurrence because `you know` can be part of the real sentence.

Normalization prepares text for Hindi translation, especially for simple cases around spacing, numbers, times, dates, and abbreviations.

### 6. Protected Terms

Code path:

```text
speech_to_text.protected_terms.ProtectedTermService.protect()
```

Protected terms solve the named entity problem. Terms like `Google Meet`, `Asterisk`, company names, product names, and acronyms should often remain unchanged instead of being translated literally.

The data is stored in the database through:

```text
speech_to_text.models.ProtectedTerm
```

The service replaces matched terms with placeholders:

```text
Google Meet -> {{TERM_1}}
```

The translation model sees the placeholder, not the original term. After translation, the service restores the original protected term.

This gives us two layers of protection:

1. DB managed terms for known important names.
2. Automatic detection for title-case names and acronyms when no DB term exists.

### 7. English to Hindi Translation

Code path:

```text
translator.providers.ct2_opus_mt.CTranslate2OpusMTTranslationProvider.translate()
  -> CTranslate2 translator.translate_batch()
```

Actual model:

```text
Helsinki-NLP/opus-mt-en-hi converted to CTranslate2 format
```

Local model files:

```text
models/ct2-opus-mt-en-hi/
  model.bin
  config.json
  shared_vocabulary.json
```

Runtime settings are read from `config/settings.py`:

```python
OPUS_MT_MODEL = "Helsinki-NLP/opus-mt-en-hi"
CT2_OPUS_MT_MODEL_DIR = "models/ct2-opus-mt-en-hi"
CT2_OPUS_MT_DEVICE = "cpu"
CT2_OPUS_MT_COMPUTE_TYPE = "int8"
CT2_OPUS_MT_BEAM_SIZE = 1
CT2_OPUS_MT_MAX_DECODING_LENGTH = 80
```

The first run converts the Hugging Face model into the local CTranslate2 model directory. Later runs reuse the converted model. The pipeline emits `translation.final`.

### 8. Hindi Text to Speech

Code path:

```text
text_to_speech.orchestrator.TTSOrchestrator.synthesize()
  -> text_to_speech.providers.espeak.EspeakHindiTTSProvider.synthesize()
  -> espeak-ng
```

Actual TTS runtime:

```text
system espeak-ng binary with Hindi voice
```

Settings are read from `config/settings.py`:

```python
ESPEAK_HINDI_VOICE = "hi"
ESPEAK_HINDI_SPEED = 155
ESPEAK_HINDI_PITCH = 50
```

eSpeak is not the most natural Hindi voice, but it is lightweight, local, fast, and good enough for a prototype without pulling a large neural TTS stack. The pipeline emits `tts.audio`.

## Provider Design

The model providers are created through:

```text
pipeline.provider_registry.ProviderRegistry
```

Current providers:

```text
ASR:
  faster_whisper

Translation:
  ct2_opus_mt
  opus_mt

TTS:
  espeak_hindi
```

The pipeline does not directly know model-specific setup details. It asks the registry for providers and calls the shared provider methods. This keeps the orchestration logic separate from model loading, tokenizer handling, and system binary execution.

There is no mock provider in the active design.

## Events

The backend communicates progress through WebSocket events:

```text
session.ready
pipeline.stage
asr.final
segment.skipped
translation.final
tts.audio
metrics.latency
interruption.detected
session.cancelled
error
```

These events let the frontend show meaningful status instead of appearing stuck.

## Interruption Handling

Interruption handling is managed by:

```text
streaming.playback_interruptions.PlaybackInterruptionController
```

The frontend tells the backend when TTS playback starts and stops:

```text
playback.started
playback.stopped
```

If the backend receives new user speech while TTS playback is active, it emits:

```text
interruption.detected
```

The frontend can then stop current TTS playback and clear queued audio. This is the beginning of barge-in support, where the user can interrupt the translated speech output.

## Latency and Timeouts

Each major stage records latency:

```text
vadMs
asrMs
translationMs
ttsMs
```

The metrics are emitted through `metrics.latency`.

Timeouts are defined in `config/settings.py`:

```python
ASR_TIMEOUT_MS
TRANSLATION_TIMEOUT_MS
TRANSLATION_WARMUP_TIMEOUT_MS
TTS_TIMEOUT_MS
```

These protect the WebSocket from waiting forever if a model call gets stuck or the local machine is too slow.

## Data Storage

After a session is processed, artifacts are saved by:

```text
storage.session_artifacts.SessionArtifactRecorder
  -> storage.artifacts.ProcessingArtifactStore
```

Output structure:

```text
data/audio/raw_input_audio/
  raw input audio

data/processed_audio_text/
  English ASR text

data/processed_hindi_text/
  Hindi translated text

data/processed_hindi_audio/
  Hindi WAV audio

data/events/
  WebSocket event trace
```

This makes debugging easy. For a single run, we can inspect the raw input, the ASR result, the translation result, the generated audio, and the exact event sequence.

## Edge Case Handling

Strong accents or fast speech:

The system uses faster-whisper with beam search and VAD filtering. ASR confidence is checked before translation. Low confidence chunks are skipped instead of producing bad Hindi audio.

Named entities:

Known names are stored in the `ProtectedTerm` DB table. The protected term service replaces them with placeholders before translation and restores them afterward.

Partial or incomplete speech:

The current prototype waits for `audio.end` and then processes VAD-sized chunks. This avoids translating unstable partial phrases into broken Hindi.

Fillers:

The preprocessor removes simple fillers and handles ambiguous phrases like `you know` conservatively.

Latency buildup:

The pipeline emits latency metrics for VAD, ASR, translation, and TTS. Translation warm-up happens on WebSocket connect so the first spoken request is less likely to stall after ASR.

Tone:

Tone is stored in the session and passed through the translation contract. The current OPUS-MT model is not strongly prompt-controlled, so tone support is structurally present but limited by the model.

Numbers, dates, and abbreviations:

Normalization prepares common forms before translation, and acronyms can be protected so they are not mistranslated.

User speech overlapping TTS:

Playback state messages allow the backend to detect speech while TTS is active and emit an interruption event.

## Current Limitations

- Processing starts after `audio.end`, so this is not true continuous simultaneous interpretation yet.
- eSpeak Hindi audio is lightweight but robotic.
- Tone control is limited by the OPUS-MT model.
- The cancel button stops the user-facing session and prevents stale events from being sent, but it may not instantly kill a native model call already running in a worker thread.
- The current setup is optimized for a local prototype, not high-concurrency production traffic.

## Why This Design Works For The Prototype

The system keeps the model-heavy work behind small provider classes and keeps business concerns separated into focused Django apps. The WebSocket consumer only manages live session communication. The pipeline only coordinates stages. ASR, translation, and TTS each own their own implementation details.

This makes the code understandable, easy to debug, and replaceable later. For example, we can swap eSpeak with a better Hindi neural TTS engine, or replace OPUS-MT with a stronger translation model, without rewriting the WebSocket protocol or session handling.
