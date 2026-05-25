"""Parse ingredients and instructions from recipe page text."""

from __future__ import annotations

import math
import re

from app.schemas.ingredient import ParsedIngredient, ParsedRecipe

INGREDIENT_SECTION_KEYWORDS = (
    "ingredients",
    "ingrédients",
    "liste de courses",
    "courses",
)

INSTRUCTION_SECTION_KEYWORDS = (
    "preparation",
    "préparation",
    "instructions",
    "etapes",
    "étapes",
    "methode",
    "méthode",
)

SERVINGS_PATTERNS = (
    re.compile(r"pour\s+(\d+(?:[.,]\d+)?)\s+personnes?", re.IGNORECASE),
    re.compile(r"(\d+(?:[.,]\d+)?)\s+portions?", re.IGNORECASE),
    re.compile(r"portions?\s*[:：]\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE),
    re.compile(r"recette\s+pour\s+(\d+(?:[.,]\d+)?)", re.IGNORECASE),
)

FRACTION_PATTERN = re.compile(r"(\d+)\s*/\s*(\d+)")
DECIMAL_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)")
UNIT_PATTERN = re.compile(
    r"^(?P<quantity>\d+(?:[.,]\d+)?|\d+\s*/\s*\d+)\s*"
    r"(?P<unit>c\.?\s*à\s*s\.?|c\.?\s*à\s*c\.?|cs|cc|g|kg|mg|ml|cl|l|dl|"
    r"pi[eè]ce?s?|gousse?s?|botte?s?|tranche?s?|boite?s?|"
    r"cuill[eè]re?s?\s+[àa]\s+soupe|cuill[eè]re?s?\s+[àa]\s+caf[eé]|"
    r"tbsp|tsp)\b\.?\s*(?:de\s+|d['’]\s*)?",
    re.IGNORECASE,
)
QUANTITY_THEN_NAME = re.compile(
    r"^(?P<quantity>\d+(?:[.,]\d+)?|\d+\s*/\s*\d+)\s+"
    r"(?:(?P<unit>pi[eè]ce?s?|gousse?s?|botte?s?|tranche?s?)\s+)?"
    r"(?:de\s+|d['’]\s*)?"
    r"(?P<name>.+)$",
    re.IGNORECASE,
)
OPTIONAL_PATTERN = re.compile(r"\b(facultatif|optionnel|au\s+besoin)\b", re.IGNORECASE)
BULLET_PREFIX = re.compile(r"^[\-\*•·]\s*")
NUMBERED_PREFIX = re.compile(r"^\d+[\.)]\s*")


class RecipeParserService:
    """Extract structured data from free-form recipe page text."""

    def parse(self, content: str) -> ParsedRecipe:
        lines = [line.strip() for line in content.splitlines()]
        servings = self._detect_servings(content) or 2

        ingredient_lines, instruction_lines = self._split_sections(lines)
        ingredients = [self._parse_ingredient_line(line) for line in ingredient_lines if line.strip()]
        ingredients = [item for item in ingredients if item.name or item.raw_text]

        instructions = [line for line in instruction_lines if line.strip()]
        return ParsedRecipe(servings=servings, ingredients=ingredients, instructions=instructions)

    def _detect_servings(self, content: str) -> int | None:
        for pattern in SERVINGS_PATTERNS:
            match = pattern.search(content)
            if match:
                return self._parse_number(match.group(1))
        return None

    def _split_sections(self, lines: list[str]) -> tuple[list[str], list[str]]:
        ingredient_lines: list[str] = []
        instruction_lines: list[str] = []
        current: str | None = None

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            heading = self._strip_heading_markers(line)
            lower_heading = heading.lower()

            if self._matches_keywords(lower_heading, INGREDIENT_SECTION_KEYWORDS):
                current = "ingredients"
                continue
            if self._matches_keywords(lower_heading, INSTRUCTION_SECTION_KEYWORDS):
                current = "instructions"
                continue
            if line.startswith("#") and current is not None:
                current = None

            if current == "ingredients":
                ingredient_lines.append(line)
            elif current == "instructions":
                instruction_lines.append(line)

        if not ingredient_lines:
            ingredient_lines = [
                line
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            ]

        return ingredient_lines, instruction_lines

    def _parse_ingredient_line(self, line: str) -> ParsedIngredient:
        raw_text = line.strip()
        cleaned = BULLET_PREFIX.sub("", raw_text)
        cleaned = NUMBERED_PREFIX.sub("", cleaned).strip()
        optional = bool(OPTIONAL_PATTERN.search(cleaned))
        cleaned = OPTIONAL_PATTERN.sub("", cleaned).strip(" ,")

        unit_match = UNIT_PATTERN.match(cleaned)
        if unit_match:
            quantity = self._parse_number(unit_match.group("quantity"))
            unit = self._normalize_unit(unit_match.group("unit"))
            name = cleaned[unit_match.end() :].strip()
            return ParsedIngredient(
                name=name or cleaned,
                quantity=quantity,
                unit=unit,
                raw_text=raw_text,
                optional=optional,
            )

        qty_match = QUANTITY_THEN_NAME.match(cleaned)
        if qty_match:
            quantity = self._parse_number(qty_match.group("quantity"))
            unit = qty_match.group("unit")
            name = qty_match.group("name").strip()
            normalized_unit = self._normalize_unit(unit) if unit else "piece"
            return ParsedIngredient(
                name=name,
                quantity=quantity,
                unit=normalized_unit,
                raw_text=raw_text,
                optional=optional,
            )

        leading_number = DECIMAL_PATTERN.match(cleaned)
        if leading_number:
            quantity = self._parse_number(leading_number.group(1))
            remainder = cleaned[leading_number.end() :].strip()
            remainder = re.sub(r"^(?:de\s+|d['’]\s*)", "", remainder, flags=re.IGNORECASE)
            return ParsedIngredient(
                name=remainder or cleaned,
                quantity=quantity,
                unit="piece",
                raw_text=raw_text,
                optional=optional,
            )

        return ParsedIngredient(
            name=cleaned,
            quantity=None,
            unit=None,
            raw_text=raw_text,
            optional=optional,
        )

    def _parse_number(self, value: str) -> float:
        fraction = FRACTION_PATTERN.fullmatch(value.strip())
        if fraction:
            numerator = float(fraction.group(1))
            denominator = float(fraction.group(2))
            return numerator / denominator if denominator else numerator

        normalized = value.replace(",", ".")
        number = float(normalized)
        if math.isfinite(number):
            return number
        raise ValueError(f"Invalid number: {value}")

    def _normalize_unit(self, unit: str | None) -> str | None:
        if not unit:
            return None
        normalized = unit.lower().strip().replace(".", "")
        normalized = normalized.replace("à", "a")
        mapping = {
            "c a s": "cs",
            "cas": "cs",
            "cs": "cs",
            "c a c": "cc",
            "cac": "cc",
            "cc": "cc",
            "cuillere a soupe": "cs",
            "cuillere a cafe": "cc",
            "cuilleres a soupe": "cs",
            "cuilleres a cafe": "cc",
            "tbsp": "cs",
            "tsp": "cc",
            "piece": "piece",
            "pieces": "piece",
            "pièce": "piece",
            "pièces": "piece",
            "gousse": "gousse",
            "gousses": "gousse",
            "botte": "botte",
            "bottes": "botte",
            "tranche": "tranche",
            "tranches": "tranche",
            "boite": "boite",
            "boites": "boite",
        }
        return mapping.get(normalized, normalized)

    @staticmethod
    def _strip_heading_markers(line: str) -> str:
        return re.sub(r"^#+\s*", "", line).strip()

    @staticmethod
    def _matches_keywords(text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)
