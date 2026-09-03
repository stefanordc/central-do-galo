from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Central do Galo API"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    db_host: str
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str
    db_password: str
    db_sslmode: str = "require"

    news_collection_enabled: bool = True
    news_collection_interval_seconds: int = 300
    news_collection_initial_delay_seconds: int = 2
    news_collection_request_delay_seconds: float = 0.6

    # YouTube: coleta pública de metadados das abas Vídeos, Shorts e Lives.
    youtube_sync_enabled: bool = True
    youtube_sync_interval_seconds: int = 900
    youtube_sync_initial_delay_seconds: int = 8
    youtube_items_per_section: int = 10
    youtube_scrape_headless: bool = True
    youtube_scrape_page_timeout_seconds: float = 45.0
    youtube_scrape_wait_seconds: float = 20.0
    youtube_scrape_scroll_pause_seconds: float = 1.5
    youtube_scrape_max_scrolls: int = 6
    youtube_scrape_profile_dir: str = ".youtube_public_uc_profile"
    youtube_scrape_debug_enabled: bool = True
    youtube_scrape_debug_dir: str = ".youtube_debug"

    # Radar do X. O padrão atual é SeleniumBase UC público + oEmbed nativo.
    # A fonte oficial via X API pode ser reativada futuramente com X_SOURCE=x_api_v2.
    x_source: str = "scrape"
    x_bearer_token: str | None = None
    x_sync_secret: str | None = None
    x_sync_enabled: bool = True
    x_sync_interval_seconds: int = 900
    x_sync_initial_delay_seconds: int = 5
    x_sync_timeout_seconds: float = 30.0
    x_sync_fetch_limit: int = 10

    # Coleta pública no x.com via SeleniumBase UC, sem login.
    x_scrape_interval_seconds: int = 3600
    x_scrape_initial_delay_seconds: int = 15
    x_scrape_page_timeout_seconds: float = 45.0
    x_scrape_delay_between_accounts_seconds: float = 30.0
    x_scrape_posts_per_account: int = 3
    x_scrape_request_retries: int = 1
    x_scrape_retry_backoff_seconds: float = 10.0
    # Renderização/diagnóstico do DOM público do X.
    x_scrape_render_wait_seconds: float = 2.0
    x_scrape_timeline_wait_seconds: float = 18.0
    x_scrape_scroll_pause_seconds: float = 2.5
    x_scrape_profile_dir: str = ".x_public_uc_profile"
    x_scrape_debug_enabled: bool = True
    x_scrape_debug_dir: str = ".radar_x_debug"
    x_scrape_max_scrolls: int = 6
    x_scrape_headless: bool = True
    x_scrape_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return (
            f"postgresql://{user}:{password}@{self.db_host}:{self.db_port}/"
            f"{self.db_name}?sslmode={self.db_sslmode}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
