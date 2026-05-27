"""Parse recipe content using Google Gemini."""

from __future__ import annotations

import json
import logging
import re

import httpx

from app.core.config import get_settings
from app.schemas.ingredient import ParsedIngredient, ParsedRecipe

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

ALLOWED_UNITS = frozenset(
    {"g", "kg", "mg", "ml", "cl", "l", "dl", "cs", "cc", "piece", "gousse", "botte", "tranche", "boite"}
)

PARSED_RECIPE_SCHEMA = {
    "type": "object",
    "properties": {
        "servings": {"type": "integer"},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "number", "nullable": True},
                    "unit": {"type": "string", "nullable": True},
                    "optional": {"type": "boolean"},
                    "raw_text": {"type": "string"},
                },
                "required": ["name", "raw_text"],
            },
        },
        "instructions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["servings", "ingredients"],
}


class GeminiRecipeParserError(Exception):
    """Raised when Gemini cannot parse recipe content."""


class GeminiRecipeParserService:
    """Extract structured recipe data from Notion page text via Gemini."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.gemini_api_key
        self._model = settings.gemini_model

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def parse(self, content: str, *, recipe_name: str = "") -> ParsedRecipe:
        if not self.configured:
            raise GeminiRecipeParserError("GEMINI_API_KEY is not configured.")

        prompt = self._build_prompt(content, recipe_name)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": PARSED_RECIPE_SCHEMA,
                "temperature": 0.1,
            },
        }

        url = GEMINI_API_URL.format(model=self._model)
        try:
            response = httpx.post(
                url,
                params={"key": self._api_key},
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise GeminiRecipeParserError(f"Gemini API request failed: {exc}") from exc

        try:
            body = response.json()
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise GeminiRecipeParserError(f"Invalid Gemini response: {exc}") from exc

        return self._to_parsed_recipe(data)

    def _build_prompt(self, content: str, recipe_name: str) -> str:
        title = recipe_name or "Recette"
        return f"""Tu es un assistant culinaire. Analyse le texte brut d'une page recette Notion et extrais UNIQUEMENT les ingrédients à acheter.

Recette : {title}

Règles strictes :
- Extraire seulement les ingrédients alimentaires ou produits achetés en magasin.
- Ignorer : métadonnées (portions, temps de préparation/cuisson, saison, mois), étapes de préparation, conseils, restes, recettes compatibles, listes "ingrédients à réutiliser".
- servings = nombre de personnes pour la recette (entier >= 1). Cherche "Portions", "Pour X personnes", etc.
- Chaque ingrédient : name (nom lisible), quantity (nombre ou null), unit (g, kg, ml, cl, l, dl, cs, cc, piece, gousse, botte, tranche, boite, ou null), optional (true si facultatif/optionnel), raw_text (ligne source).
- Ne pas inventer d'ingrédients absents du texte.
- instructions : liste courte des étapes (optionnel, peut être vide).

Texte Notion :
\"\"\"
{content.strip()}
\"\"\"
"""

    def _to_parsed_recipe(self, data: dict) -> ParsedRecipe:
        servings = int(data.get("servings") or 2)
        if servings < 1:
            servings = 2

        ingredients: list[ParsedIngredient] = []
        for item in data.get("ingredients") or []:
            name = str(item.get("name") or "").strip()
            raw_text = str(item.get("raw_text") or name).strip()
            if not name and not raw_text:
                continue

            quantity = item.get("quantity")
            if quantity is not None:
                try:
                    quantity = float(quantity)
                except (TypeError, ValueError):
                    quantity = None

            unit = item.get("unit")
            if unit is not None:
                unit = self._normalize_unit(str(unit))
                if unit not in ALLOWED_UNITS:
                    unit = "piece" if unit else None

            ingredients.append(
                ParsedIngredient(
                    name=name or raw_text,
                    quantity=quantity,
                    unit=unit,
                    raw_text=raw_text,
                    optional=bool(item.get("optional")),
                )
            )

        instructions = [
            str(step).strip()
            for step in data.get("instructions") or []
            if str(step).strip()
        ]

        if not ingredients:
            raise GeminiRecipeParserError("Gemini returned no ingredients.")

        return ParsedRecipe(servings=servings, ingredients=ingredients, instructions=instructions)

    @staticmethod
    def _normalize_unit(unit: str) -> str | None:
        normalized = unit.lower().strip().replace(".", "")
        normalized = re.sub(r"\s+", " ", normalized)
        mapping = {
            "cuillere a soupe": "cs",
            "cuillere a cafe": "cc",
            "cuilleres a soupe": "cs",
            "cuilleres a cafe": "cc",
            "c a s": "cs",
            "c a c": "cc",
            "cas": "cs",
            "cac": "cc",
            "tbsp": "cs",
            "tsp": "cc",
            "pieces": "piece",
            "pièce": "piece",
            "pièces": "piece",
            "gousses": "gousse",
            "bottes": "botte",
            "tranches": "tranche",
            "boites": "boite",
            "boîte": "boite",
            "boîtes": "boite",
        }
        return mapping.get(normalized, normalized.replace(" ", "") if normalized else None)
