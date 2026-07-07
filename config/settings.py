import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-secret-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "channels",
    "sessions.apps.SessionsConfig",
    "streaming.apps.StreamingConfig",
    "speech_to_text.apps.SpeechToTextConfig",
    "translator.apps.TranslatorConfig",
    "text_to_speech.apps.TextToSpeechConfig",
    "pipeline.apps.PipelineConfig",
    "observability.apps.ObservabilityConfig",
    "storage.apps.StorageConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.environ.get("DB_NAME", str(BASE_DIR / "db.sqlite3")),
        "USER": os.environ.get("DB_USER", ""),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", ""),
        "PORT": os.environ.get("DB_PORT", ""),
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": os.environ.get(
            "CHANNEL_LAYER_BACKEND",
            "channels.layers.InMemoryChannelLayer",
        ),
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")],
        },
    }
}

if CHANNEL_LAYERS["default"]["BACKEND"] == "channels.layers.InMemoryChannelLayer":
    CHANNEL_LAYERS["default"].pop("CONFIG", None)

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("APP_TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
}

SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "1800"))
MAX_AUDIO_FRAME_BYTES = int(os.environ.get("MAX_AUDIO_FRAME_BYTES", "262144"))
MAX_INVALID_MESSAGES = int(os.environ.get("MAX_INVALID_MESSAGES", "3"))
PROTECTED_TERM_CACHE_SECONDS = int(os.environ.get("PROTECTED_TERM_CACHE_SECONDS", "30"))
PROCESSING_DATA_ROOT = Path(os.environ.get("PROCESSING_DATA_ROOT", str(BASE_DIR / "data")))

PROVIDER_CONFIG = {
    "asr": os.environ.get("ASR_PROVIDER", "faster_whisper"),
    "translation": os.environ.get("TRANSLATION_PROVIDER", "ct2_opus_mt"),
    "tts": os.environ.get("TTS_PROVIDER", "espeak_hindi"),
}

ASR_TIMEOUT_MS = int(os.environ.get("ASR_TIMEOUT_MS", "180000"))
TRANSLATION_TIMEOUT_MS = int(os.environ.get("TRANSLATION_TIMEOUT_MS", "12000"))
TRANSLATION_WARMUP_TIMEOUT_MS = int(os.environ.get("TRANSLATION_WARMUP_TIMEOUT_MS", "90000"))
TTS_TIMEOUT_MS = int(os.environ.get("TTS_TIMEOUT_MS", "60000"))

FASTER_WHISPER_MODEL = os.environ.get("FASTER_WHISPER_MODEL", "tiny.en")
FASTER_WHISPER_DEVICE = os.environ.get("FASTER_WHISPER_DEVICE", "cpu")
FASTER_WHISPER_COMPUTE_TYPE = os.environ.get("FASTER_WHISPER_COMPUTE_TYPE", "int8")
FASTER_WHISPER_BEAM_SIZE = int(os.environ.get("FASTER_WHISPER_BEAM_SIZE", "5"))

OPUS_MT_MODEL = os.environ.get("OPUS_MT_MODEL", "Helsinki-NLP/opus-mt-en-hi")
OPUS_MT_DEVICE = os.environ.get("OPUS_MT_DEVICE", "auto")
OPUS_MT_MAX_NEW_TOKENS = int(os.environ.get("OPUS_MT_MAX_NEW_TOKENS", "80"))
OPUS_MT_NUM_BEAMS = int(os.environ.get("OPUS_MT_NUM_BEAMS", "1"))

CT2_OPUS_MT_MODEL_DIR = os.environ.get(
    "CT2_OPUS_MT_MODEL_DIR",
    str(BASE_DIR / "models" / "ct2-opus-mt-en-hi"),
)
CT2_OPUS_MT_DEVICE = os.environ.get("CT2_OPUS_MT_DEVICE", "cpu")
CT2_OPUS_MT_COMPUTE_TYPE = os.environ.get("CT2_OPUS_MT_COMPUTE_TYPE", "int8")
CT2_OPUS_MT_QUANTIZATION = os.environ.get("CT2_OPUS_MT_QUANTIZATION", "int8")
CT2_OPUS_MT_BEAM_SIZE = int(os.environ.get("CT2_OPUS_MT_BEAM_SIZE", "1"))
CT2_OPUS_MT_MAX_DECODING_LENGTH = int(os.environ.get("CT2_OPUS_MT_MAX_DECODING_LENGTH", "80"))

ESPEAK_HINDI_VOICE = os.environ.get("ESPEAK_HINDI_VOICE", "hi")
ESPEAK_HINDI_SPEED = int(os.environ.get("ESPEAK_HINDI_SPEED", "155"))
ESPEAK_HINDI_PITCH = int(os.environ.get("ESPEAK_HINDI_PITCH", "50"))
