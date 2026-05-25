"""Save a manual mon-marché.fr browser session for Playwright."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    storage_path = settings.monmarche_storage_state_file
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    print("Opening mon-marché.fr in a headed Chromium window.")
    print("Log in manually in the browser. Do not enter your password in this terminal.")
    print("When you are logged in, return here and press Enter to save the session.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(settings.monmarche_base_url)
        input("\nPress Enter after you have logged in successfully...")
        context.storage_state(path=str(storage_path))
        browser.close()

    print(f"Session saved to {storage_path}")


if __name__ == "__main__":
    main()
