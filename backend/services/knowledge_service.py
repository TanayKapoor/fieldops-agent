"""Score a user's question against knowledge.md's sections and decide whether
the assistant is allowed to answer from it.

Pure function, no LLM/API calls, no dependency on work_order_repo.py or any
other layer — fully testable standalone.

CRITICAL DOWNSTREAM CONTRACT: when search() returns (None, score), the caller
(conversation_service.py) must pass NO section text into the LLM prompt —
only an explicit NO_MATCH instruction. A low-score section must never be
passed through "just in case." This module only returns the signal; it does
not and cannot enforce that the caller honors it.
"""

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
    "what", "who", "how", "someone", "else",
}


@dataclass(frozen=True)
class Section:
    heading: str
    body: str
    keywords: frozenset[str]


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _parse_sections(text: str) -> list[Section]:
    # split on level-2 headings ("## 1. Unit Reset Procedure..."); text before
    # the first heading (title, intro) is discarded
    chunks = re.split(r"^## +(.+)$", text, flags=re.MULTILINE)[1:]
    sections = []
    for heading, body in zip(chunks[0::2], chunks[1::2]):
        heading = heading.strip()
        body = body.strip()
        keywords = frozenset(_tokenize(f"{heading} {body}"))
        sections.append(Section(heading=heading, body=body, keywords=keywords))
    return sections


def _build_doc_freq(sections: list[Section]) -> dict[str, int]:
    doc_freq: dict[str, int] = {}
    for section in sections:
        for kw in section.keywords:
            doc_freq[kw] = doc_freq.get(kw, 0) + 1
    return doc_freq


_SECTIONS = _parse_sections(_KNOWLEDGE_PATH.read_text())
_DOC_FREQ = _build_doc_freq(_SECTIONS)
_NUM_SECTIONS = len(_SECTIONS)


def _idf(term: str) -> float:
    df = _DOC_FREQ.get(term, 0)
    if df == 0:
        return 0.0
    return _NUM_SECTIONS / df


def search(query: str) -> tuple[Section | None, float]:
    """Returns (best_matching_section, score).
    If no section clears the threshold, returns (None, best_score_seen)."""
    query_tokens = _tokenize(query)
    best_section: Section | None = None
    best_score = 0.0

    for section in _SECTIONS:
        overlap = query_tokens & section.keywords
        score = sum(_idf(term) for term in overlap)
        if score > best_score:
            best_section = section
            best_score = score

    if best_score >= MIN_SCORE_THRESHOLD:
        return best_section, best_score
    return None, best_score
