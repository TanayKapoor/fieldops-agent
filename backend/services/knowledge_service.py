"""Section parsing + weighted keyword scoring (grounding).

Parses knowledge.md into its ##-headed sections at import time, then scores
free-text queries against those sections by summed IDF-weight of overlapping
keywords. Pure function, zero LLM/API dependency — testable standalone.

conversation_service.py calls search() and decides what to inject into the
prompt based on the result. On no-match (score below threshold), the caller
must NOT pass any section text into the prompt — pass an explicit NO_MATCH
marker/instruction instead, so the model is structurally forced to say
"not covered," rather than merely told to.
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path

MIN_SCORE_THRESHOLD = 2.0

_KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "knowledge.md"

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "at", "by", "for", "with", "and", "or", "if",
    "it", "its", "this", "that", "these", "those", "do", "does", "did",
    "not", "no", "you", "your", "i", "we", "should", "must", "can", "will",
}


@dataclass(frozen=True)
class Section:
    title: str
    body: str
    keywords: frozenset[str]


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _parse_sections(text: str) -> list[Section]:
    # split on level-2 headers ("## ..."); ignore preamble before the first one
    chunks = re.split(r"^## +(.+)$", text, flags=re.MULTILINE)[1:]
    sections = []
    for title, body in zip(chunks[0::2], chunks[1::2]):
        body = body.strip()
        sections.append(Section(title=title.strip(), body=body, keywords=frozenset(_tokenize(f"{title} {body}"))))
    return sections


def _build_idf(sections: list[Section]) -> dict[str, float]:
    n = len(sections)
    doc_freq: dict[str, int] = {}
    for section in sections:
        for kw in section.keywords:
            doc_freq[kw] = doc_freq.get(kw, 0) + 1
    # +1 smoothing so a keyword in every section still gets a small positive weight
    return {kw: math.log((n + 1) / (df + 1)) + 1 for kw, df in doc_freq.items()}


_SECTIONS = _parse_sections(_KNOWLEDGE_PATH.read_text())
_IDF = _build_idf(_SECTIONS)


def search(query: str) -> tuple[Section | None, float]:
    query_tokens = _tokenize(query)
    best_section: Section | None = None
    best_score = 0.0

    for section in _SECTIONS:
        overlap = query_tokens & section.keywords
        score = sum(_IDF.get(kw, 0.0) for kw in overlap)
        if score > best_score:
            best_section = section
            best_score = score

    if best_score >= MIN_SCORE_THRESHOLD:
        return best_section, best_score
    return None, best_score
