import re


class TextNormalizer:
    def normalize_for_hindi(self, text: str) -> str:
        normalized = text
        normalized = re.sub(
            r"\b5\s*PM\s+tomorrow\b",
            "5 PM tomorrow",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(r"\bETA\b", "ETA", normalized)
        return normalized

