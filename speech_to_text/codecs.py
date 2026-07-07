class UnsupportedAudioFormat(ValueError):
    pass


class AudioCodecService:
    def decode_to_pcm(self, data: bytes, fmt: str) -> bytes:
        if fmt == "pcm16":
            return data
        if fmt == "opus":
            # Placeholder adapter boundary: plug in an Opus decoder here.
            return data
        raise UnsupportedAudioFormat("Unsupported audio format: %s" % fmt)

