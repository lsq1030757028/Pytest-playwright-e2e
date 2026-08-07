from __future__ import annotations

import re
import unicodedata

_CONTROL_PHRASES = (
    "ignore previous",
    "ignore all policies",
    "disregard previous instructions",
    "override policy",
    "bypass policy",
    "grant permission",
    "elevate permission",
    "system prompt",
    "reveal system prompt",
    "execute shell",
    "run shell command",
)


def normalize_control_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Cf"
    )
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def contains_control_instruction(value: str) -> bool:
    normalized = normalize_control_text(value)
    return any(phrase in normalized for phrase in _CONTROL_PHRASES)
