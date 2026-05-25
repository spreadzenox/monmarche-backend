"""Playwright automation skeleton for mon-marché.fr cart preparation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from app.core.config import get_settings
from app.schemas.order import PrepareCartProductResult

logger = logging.getLogger(__name__)


class MonMarcheSelectors:
    """Centralized selectors for mon-marché.fr (to be refined with real DOM)."""

    SEARCH_INPUT = "input[type='search'], input[name='search'], #search"
    ADD_TO_CART_BUTTON = (
        "button:has-text('Ajouter au panier'), "
        "button[data-testid='add-to-cart'], "
        ".add-to-cart"
    )
    CART_LINK = "a[href*='panier']"


class MonMarcheBotError(Exception):
    """Raised when cart preparation cannot proceed."""


@dataclass
class CartPreparationResult:
    cart_url: str
    checkout_url: str | None = None
    added_products: list[PrepareCartProductResult] = field(default_factory=list)
    failed_products: list[PrepareCartProductResult] = field(default_factory=list)


class MonMarcheBot:
    """Isolated Playwright layer. Never handles payment or credentials."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._selectors = MonMarcheSelectors()
        self._debug_dir = self._settings.debug_dir
        self._debug_dir.mkdir(parents=True, exist_ok=True)

    def prepare_cart(self, products: list[dict[str, Any]]) -> CartPreparationResult:
        storage_path = self._settings.monmarche_storage_state_file
        if not storage_path.exists():
            raise MonMarcheBotError(
                "Mon Marché session not found. Run "
                "'python scripts/save_monmarche_session.py' and log in manually in the browser."
            )

        added: list[PrepareCartProductResult] = []
        failed: list[PrepareCartProductResult] = []

        with sync_playwright() as playwright:
            browser = self._launch_browser(playwright, storage_path)
            try:
                context = browser.new_context(storage_state=str(storage_path))
                page = context.new_page()
                page.goto(self._settings.monmarche_base_url, wait_until="domcontentloaded")

                for index, product in enumerate(products):
                    ingredient = product.get("ingredient", "unknown")
                    product_name = product.get("product_name", ingredient)
                    product_url = product.get("product_url")
                    search_query = product.get("search_query", ingredient)
                    quantity = int(product.get("quantity_to_add", 1))

                    try:
                        self._add_product(page, product_url=product_url, search_query=search_query)
                        self._take_debug_screenshot(page, f"product_{index}_{ingredient}")
                        added.append(
                            PrepareCartProductResult(
                                ingredient=ingredient,
                                product_name=product_name,
                                product_url=product_url,
                                success=True,
                                message=f"Prepared add-to-cart flow for quantity {quantity}",
                            )
                        )
                    except Exception as exc:
                        logger.exception("Failed to prepare product %s", ingredient)
                        self._take_debug_screenshot(page, f"failed_{index}_{ingredient}")
                        failed.append(
                            PrepareCartProductResult(
                                ingredient=ingredient,
                                product_name=product_name,
                                product_url=product_url,
                                success=False,
                                message=str(exc),
                            )
                        )

                cart_url = self._open_cart(page)
                self._take_debug_screenshot(page, "cart")
            finally:
                browser.close()

        return CartPreparationResult(
            cart_url=cart_url,
            checkout_url=None,
            added_products=added,
            failed_products=failed,
        )

    def _launch_browser(self, playwright: Playwright, storage_path: Path) -> Browser:
        return playwright.chromium.launch(headless=True)

    def _add_product(self, page: Page, *, product_url: str | None, search_query: str) -> None:
        if product_url:
            page.goto(product_url, wait_until="domcontentloaded")
        else:
            page.goto(self._settings.monmarche_base_url, wait_until="domcontentloaded")
            self._search_product(page, search_query)

        self._click_add_to_cart(page)

    def _search_product(self, page: Page, search_query: str) -> None:
        search_input = page.locator(self._selectors.SEARCH_INPUT).first
        if search_input.count() == 0:
            raise MonMarcheBotError(
                f"Search input not found on mon-marché.fr. Update selectors in MonMarcheBot."
            )
        search_input.fill(search_query)
        search_input.press("Enter")
        page.wait_for_load_state("domcontentloaded")

    def _click_add_to_cart(self, page: Page) -> None:
        button = page.locator(self._selectors.ADD_TO_CART_BUTTON).first
        if button.count() == 0:
            raise MonMarcheBotError(
                "Add to cart button not found. Real selectors must be configured before production use."
            )
        button.click()
        page.wait_for_timeout(1000)

    def _open_cart(self, page: Page) -> str:
        page.goto(self._settings.monmarche_cart_url, wait_until="domcontentloaded")
        return page.url or self._settings.monmarche_cart_url

    def _take_debug_screenshot(self, page: Page, label: str) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = "".join(char if char.isalnum() or char in "-_" else "_" for char in label)
        path = self._debug_dir / f"{timestamp}_{safe_label}.png"
        try:
            page.screenshot(path=str(path), full_page=True)
            logger.info("Saved debug screenshot: %s", path)
        except Exception as exc:
            logger.warning("Could not save screenshot %s: %s", path, exc)
