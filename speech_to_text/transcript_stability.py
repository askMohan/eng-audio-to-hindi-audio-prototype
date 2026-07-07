from pipeline.contracts import ASRResult


class TranscriptStabilityChecker:
    def is_translation_ready(self, result: ASRResult) -> bool:
        if not result.text.strip():
            return False
        if result.confidence is not None and result.confidence < 0.55:
            return False
        return True
