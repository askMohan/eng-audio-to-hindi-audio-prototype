class PipelineError(Exception):
    code = "PIPELINE_ERROR"
    recoverable = True


class InvalidMessageError(PipelineError):
    code = "INVALID_MESSAGE"


class AudioDecodeError(PipelineError):
    code = "AUDIO_DECODE_FAILED"


class UnsupportedAudioFormatError(PipelineError):
    code = "UNSUPPORTED_AUDIO_FORMAT"

