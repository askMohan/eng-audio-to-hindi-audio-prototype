import re
import time
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from django.conf import settings

from pipeline.contracts import ProtectedTermMatch
from speech_to_text.models import ProtectedTerm


@dataclass(frozen=True)
class ProtectedTermEntry:
    source: str
    target: str
    aliases: Tuple[str, ...]
    mode: str


@dataclass(frozen=True)
class ProtectionResult:
    text: str
    matches: List[ProtectedTermMatch]


class ProtectedTermService:
    AUTOMATIC_ACRONYM_EXCLUSIONS = {"AM", "PM"}

    def __init__(self) -> None:
        self._cache_until = 0.0
        self._cache = []

    def get_active_terms(self) -> List[ProtectedTermEntry]:
        now = time.monotonic()
        if now < self._cache_until:
            return list(self._cache)

        rows = ProtectedTerm.objects.filter(is_active=True).order_by("source")
        self._cache = [
            ProtectedTermEntry(
                source=row.source,
                target=row.target or row.source,
                aliases=tuple(row.aliases or []),
                mode=row.mode,
            )
            for row in rows
        ]
        self._cache_until = now + settings.PROTECTED_TERM_CACHE_SECONDS
        return list(self._cache)

    def protect(self, text: str) -> ProtectionResult:
        terms = self.get_active_terms()
        candidates = self._find_catalog_matches(text, terms)
        if not candidates:
            candidates = self._find_automatic_entity_matches(text)
        return self._replace_matches(text, candidates)

    @staticmethod
    def restore(text: str, matches: Sequence[ProtectedTermMatch]) -> str:
        restored = text
        for match in matches:
            restored = restored.replace(match.placeholder, match.target)
        return restored

    def _find_catalog_matches(
        self, text: str, terms: Iterable[ProtectedTermEntry]
    ) -> List[Tuple[int, int, str, str]]:
        matches = []
        for term in terms:
            names = [term.source] + list(term.aliases)
            for name in names:
                if not name:
                    continue
                pattern = re.compile(r"\b%s\b" % re.escape(name), re.IGNORECASE)
                for found in pattern.finditer(text):
                    matches.append((found.start(), found.end(), term.source, term.target))
        return self._dedupe_overlaps(matches)

    @staticmethod
    def _find_automatic_entity_matches(text: str) -> List[Tuple[int, int, str, str]]:
        matches = []
        acronym_pattern = re.compile(r"\b[A-Z]{2,6}\b")
        title_pattern = re.compile(r"\b(?:[A-Z][a-z0-9]+)(?:\s+[A-Z][a-z0-9]+){1,3}\b")
        for pattern in (acronym_pattern, title_pattern):
            for found in pattern.finditer(text):
                value = found.group(0)
                if value.upper() in ProtectedTermService.AUTOMATIC_ACRONYM_EXCLUSIONS:
                    continue
                matches.append((found.start(), found.end(), value, value))
        return ProtectedTermService._dedupe_overlaps(matches)

    @staticmethod
    def _dedupe_overlaps(matches: List[Tuple[int, int, str, str]]) -> List[Tuple[int, int, str, str]]:
        ordered = sorted(matches, key=lambda item: (item[0], -(item[1] - item[0])))
        selected = []
        last_end = -1
        for match in ordered:
            if match[0] >= last_end:
                selected.append(match)
                last_end = match[1]
        return selected

    @staticmethod
    def _replace_matches(text: str, matches: List[Tuple[int, int, str, str]]) -> ProtectionResult:
        if not matches:
            return ProtectionResult(text=text, matches=[])
        output = []
        protected = []
        cursor = 0
        for index, (start, end, source, target) in enumerate(matches, start=1):
            placeholder = "{{TERM_%s}}" % index
            output.append(text[cursor:start])
            output.append(placeholder)
            protected.append(
                ProtectedTermMatch(
                    placeholder=placeholder,
                    source=source,
                    target=target,
                    start=start,
                    end=end,
                )
            )
            cursor = end
        output.append(text[cursor:])
        return ProtectionResult(text="".join(output), matches=protected)
