import re


class TextPreprocessor:
    SIMPLE_FILLERS = ("uh", "uhh", "um", "umm", "erm", "ah")

    def clean(self, text: str) -> str:
        cleaned = text.strip()
        cleaned = self._remove_simple_fillers(cleaned)
        cleaned = self._remove_discourse_you_know(cleaned)
        cleaned = self._remove_discourse_like(cleaned)
        cleaned = self._normalize_spacing(cleaned)
        return cleaned.strip(" ,")

    def _remove_simple_fillers(self, text: str) -> str:
        filler_group = "|".join(re.escape(filler) for filler in self.SIMPLE_FILLERS)
        return re.sub(r"\b(?:%s)\b[,\s]*" % filler_group, "", text, flags=re.IGNORECASE)

    @staticmethod
    def _remove_discourse_you_know(text: str) -> str:
        cleaned = text
        cleaned = re.sub(
            r"^\s*you know(?:,|\s{2,})\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"([,;:]\s*)you know(?=\s*[,;:])\s*[,;:]?\s*",
            r"\1",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned

    @staticmethod
    def _remove_discourse_like(text: str) -> str:
        cleaned = re.sub(r"^\s*like(?:,|\s{2,})\s*", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"([,;:]\s*)like(?=\s*[,;:])\s*[,;:]?\s*",
            r"\1",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned

    @staticmethod
    def _normalize_spacing(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text)
        cleaned = re.sub(r",\s*,+", ",", cleaned)
        cleaned = re.sub(r"\s+([,.?!;:])", r"\1", cleaned)
        cleaned = re.sub(r"([,;:])\s+([,.?!;:])", r"\2", cleaned)
        return cleaned
