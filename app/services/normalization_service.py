"""Ingredient name normalization."""

from __future__ import annotations

import re
import unicodedata

WEAK_WORDS = {
    "d",
    "du",
    "des",
    "la",
    "le",
    "les",
    "un",
    "une",
    "au",
    "aux",
    "en",
    "fin",
    "frais",
    "fraiche",
}

COMMON_REPLACEMENTS = {
    "huile olive": "huile olive",
    "pomme de terre": "pomme de terre",
    "pommes de terre": "pomme de terre",
    "gousse ail": "ail",
    "gousses ail": "ail",
    "oignon jaune": "oignon jaune",
    "oignons jaunes": "oignon jaune",
    "sel fin": "sel",
    "poivre noir": "poivre",
    "tomate cerise": "tomate cerise",
    "tomates cerises": "tomate cerise",
}


class NormalizationService:
    """Simple, readable normalization rules for ingredient names."""

    def normalize(self, name: str) -> str:
        text = name.strip().lower()
        text = text.replace("’", "'").replace("'", " ")
        text = self._remove_accents(text)
        text = re.sub(r"\s+", " ", text).strip()
        text = self._apply_phrase_replacements(text)
        text = self._remove_weak_words(text)
        text = self._normalize_plural(text)
        text = self._apply_phrase_replacements(text)
        return text

    def _apply_phrase_replacements(self, text: str) -> str:
        if text in COMMON_REPLACEMENTS:
            return COMMON_REPLACEMENTS[text]
        return text

    def _remove_accents(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        return "".join(char for char in normalized if not unicodedata.combining(char))

    def _remove_weak_words(self, text: str) -> str:
        tokens = [token for token in text.split() if token not in WEAK_WORDS]
        return " ".join(tokens).strip()

    def _normalize_plural(self, text: str) -> str:
        if text in COMMON_REPLACEMENTS:
            return COMMON_REPLACEMENTS[text]

        tokens = text.split()
        normalized_tokens: list[str] = []
        for token in tokens:
            if token.endswith("aux") and len(token) > 4:
                normalized_tokens.append(token[:-3] + "al")
            elif token.endswith("eaux") and len(token) > 5:
                normalized_tokens.append(token[:-1])
            elif token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
                normalized_tokens.append(token[:-1])
            else:
                normalized_tokens.append(token)
        candidate = " ".join(normalized_tokens)
        return COMMON_REPLACEMENTS.get(candidate, candidate)
