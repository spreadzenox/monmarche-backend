"""Notion API integration for the recipes database."""

from __future__ import annotations

import logging
from typing import Any

from notion_client import Client
from notion_client.errors import APIResponseError

from datetime import UTC, datetime

from app.core.config import NotionPropertyNames, get_settings
from app.schemas.recipe import RecipeDetail, RecipeSummary

logger = logging.getLogger(__name__)

_UNSUPPORTED_CHILD_BLOCK_TYPES = frozenset({"ai_block"})


class NotionServiceError(Exception):
    """Raised when Notion integration fails."""


class NotionService:
    """Isolates all Notion API details from the rest of the application."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.notion_token:
            raise NotionServiceError(
                "NOTION_TOKEN is not configured. Set it in your environment or .env file."
            )
        if not settings.notion_recipes_database_id:
            raise NotionServiceError(
                "NOTION_RECIPES_DATABASE_ID is not configured. "
                "Set it to the ID of the '🍛 Livre de recettes' database."
            )
        self._database_id = settings.notion_recipes_database_id.replace("-", "")
        self._client = Client(auth=settings.notion_token)
        self._props = NotionPropertyNames()
        self._data_source_id: str | None = None

    def _get_data_source_id(self) -> str:
        if self._data_source_id:
            return self._data_source_id

        try:
            database = self._client.databases.retrieve(database_id=self._database_id)
        except APIResponseError as exc:
            raise NotionServiceError(
                f"Unable to access Notion recipes database: {exc.body or exc}"
            ) from exc

        data_sources = database.get("data_sources") or []
        if not data_sources:
            raise NotionServiceError(
                f"No data source found for Notion database '{self._database_id}'."
            )

        self._data_source_id = data_sources[0]["id"].replace("-", "")
        return self._data_source_id

    def list_recipes(self) -> list[RecipeSummary]:
        try:
            pages = self._query_all_pages()
        except APIResponseError as exc:
            raise NotionServiceError(
                f"Unable to access Notion recipes database: {exc.body or exc}"
            ) from exc

        recipes: list[RecipeSummary] = []
        for page in pages:
            try:
                recipes.append(self._page_to_summary(page))
            except NotionServiceError as exc:
                logger.warning("Skipping page %s: %s", page.get("id"), exc)
        return recipes

    def get_recipe(self, page_id: str) -> RecipeDetail:
        page_id = page_id.replace("-", "")
        try:
            page = self._client.pages.retrieve(page_id=page_id)
        except APIResponseError as exc:
            raise NotionServiceError(f"Recipe page '{page_id}' not found or inaccessible.") from exc

        summary = self._page_to_summary(page)
        raw_content = self.get_page_content_text(page_id)
        return RecipeDetail(**summary.model_dump(), raw_content=raw_content)

    def get_page_raw_blocks(self, page_id: str) -> list[dict[str, Any]]:
        page_id = page_id.replace("-", "")
        blocks: list[dict[str, Any]] = []
        cursor: str | None = None

        try:
            while True:
                response = self._client.blocks.children.list(
                    block_id=page_id,
                    start_cursor=cursor,
                )
                blocks.extend(response.get("results", []))
                if not response.get("has_more"):
                    break
                cursor = response.get("next_cursor")
        except APIResponseError as exc:
            raise NotionServiceError(
                f"Unable to read content for recipe page '{page_id}': {exc.body or exc}"
            ) from exc

        return blocks

    def get_page_content_text(self, page_id: str) -> str:
        blocks = self.get_page_raw_blocks(page_id)
        return self.blocks_to_text(blocks)

    def blocks_to_text(self, blocks: list[dict[str, Any]], depth: int = 0) -> str:
        lines: list[str] = []
        indent = "  " * depth

        for block in blocks:
            block_type = block.get("type")
            if not block_type:
                continue

            if block_type in _UNSUPPORTED_CHILD_BLOCK_TYPES:
                continue

            payload = block.get(block_type, {})
            text = self._rich_text_to_plain(payload.get("rich_text", []))

            if block_type in {"heading_1", "heading_2", "heading_3"}:
                prefix = "#" * int(block_type[-1])
                lines.append(f"{indent}{prefix} {text}".strip())
            elif block_type == "bulleted_list_item":
                lines.append(f"{indent}- {text}".strip())
            elif block_type == "numbered_list_item":
                lines.append(f"{indent}1. {text}".strip())
            elif block_type == "to_do":
                checked = payload.get("checked", False)
                marker = "[x]" if checked else "[ ]"
                lines.append(f"{indent}{marker} {text}".strip())
            elif block_type == "paragraph":
                if text:
                    lines.append(f"{indent}{text}")
            elif block_type == "quote":
                lines.append(f"{indent}> {text}".strip())
            elif block_type == "divider":
                lines.append(f"{indent}---")
            elif block_type == "table":
                lines.append(f"{indent}[table]")
            else:
                if text:
                    lines.append(f"{indent}{text}")

            if block.get("has_children") and block_type not in _UNSUPPORTED_CHILD_BLOCK_TYPES:
                child_blocks = self._get_child_blocks(block["id"])
                lines.append(self.blocks_to_text(child_blocks, depth + 1))

        return "\n".join(line for line in lines if line is not None)

    def _get_child_blocks(self, block_id: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        cursor: str | None = None
        try:
            while True:
                response = self._client.blocks.children.list(
                    block_id=block_id.replace("-", ""),
                    start_cursor=cursor,
                )
                blocks.extend(response.get("results", []))
                if not response.get("has_more"):
                    break
                cursor = response.get("next_cursor")
        except APIResponseError as exc:
            logger.warning("Unable to read child blocks for %s: %s", block_id, exc)
        return blocks

    def _query_all_pages(self) -> list[dict[str, Any]]:
        data_source_id = self._get_data_source_id()
        pages: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            response = self._client.data_sources.query(
                data_source_id=data_source_id,
                start_cursor=cursor,
            )
            pages.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        return pages

    def _page_to_summary(self, page: dict[str, Any]) -> RecipeSummary:
        properties = page.get("properties", {})
        page_id = page.get("id", "").replace("-", "")

        name = self._extract_title(properties, self._props.TITLE)
        if not name:
            raise NotionServiceError(
                f"Missing or empty property '{self._props.TITLE}' on page {page_id}"
            )

        return RecipeSummary(
            id=page_id,
            name=name,
            status=self._extract_status(properties, self._props.STATUS),
            rating=self._extract_select(properties, self._props.RATING),
            tags=self._extract_multi_select(properties, self._props.TAGS),
            servings=None,
            notion_last_edited_at=self._parse_notion_datetime(page.get("last_edited_time")),
        )

    def _extract_title(self, properties: dict[str, Any], prop_name: str) -> str | None:
        prop = properties.get(prop_name)
        if not prop:
            raise NotionServiceError(f"Missing Notion property '{prop_name}'")
        if prop.get("type") != "title":
            raise NotionServiceError(f"Unexpected type for property '{prop_name}'")
        return self._rich_text_to_plain(prop.get("title", [])) or None

    def _extract_status(self, properties: dict[str, Any], prop_name: str) -> str | None:
        prop = properties.get(prop_name)
        if not prop:
            return None
        prop_type = prop.get("type")
        if prop_type == "status":
            status = prop.get("status")
            return status.get("name") if status else None
        if prop_type == "select":
            selected = prop.get("select")
            return selected.get("name") if selected else None
        return None

    def _extract_select(self, properties: dict[str, Any], prop_name: str) -> str | None:
        prop = properties.get(prop_name)
        if not prop or prop.get("type") != "select":
            return None
        selected = prop.get("select")
        return selected.get("name") if selected else None

    def _extract_multi_select(self, properties: dict[str, Any], prop_name: str) -> list[str]:
        prop = properties.get(prop_name)
        if not prop or prop.get("type") != "multi_select":
            return []
        return [item.get("name", "") for item in prop.get("multi_select", []) if item.get("name")]

    @staticmethod
    def _parse_notion_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _rich_text_to_plain(rich_text: list[dict[str, Any]]) -> str:
        return "".join(part.get("plain_text", "") for part in rich_text).strip()
