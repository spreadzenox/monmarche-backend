"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class NotionPropertyNames:
    """Centralized Notion property names for the recipes database."""

    TITLE = "Nom"
    STATUS = "État"
    RATING = "Note"
    TAGS = "Sélection multiple"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    notion_token: str = ""
    notion_recipes_database_id: str = ""

    database_url: str = "sqlite:///./monmarche.db"

    monmarche_storage_state_path: str = "./data/monmarche_storage_state.json"
    monmarche_base_url: str = "https://www.mon-marche.fr"
    monmarche_cart_url: str = "https://www.mon-marche.fr/panier"

    app_env: str = "dev"
    api_auth_token: str = ""
    auth_htpasswd_path: str = "/etc/monmarche/htpasswd"
    session_cookie_name: str = "mm_session"
    session_max_age_seconds: int = 7 * 24 * 3600
    recipes_cache_refresh_interval_seconds: int = 3600

    @property
    def notion_configured(self) -> bool:
        return bool(self.notion_token and self.notion_recipes_database_id)

    @property
    def auth_htpasswd_file(self) -> Path:
        return Path(self.auth_htpasswd_path)

    @property
    def auth_enabled(self) -> bool:
        return self.auth_htpasswd_file.is_file()

    @property
    def session_cookie_secure(self) -> bool:
        return self.app_env != "dev"

    @property
    def monmarche_storage_state_file(self) -> Path:
        return Path(self.monmarche_storage_state_path)

    @property
    def debug_dir(self) -> Path:
        return Path("./data/debug")


@lru_cache
def get_settings() -> Settings:
    return Settings()
