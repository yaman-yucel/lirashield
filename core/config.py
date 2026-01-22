from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_path: str = "data/portfolio.db"
    # tefas_chunk_days: int = 60
    # tefas_years_back: int = 5
    # yfinance_tickers: tuple[str, ...] = ("USDTRY=X", "TRY=X")


_settings_instance = None


def init_settings() -> Settings:
    """
    Initialize and cache the Settings singleton. Idempotent.
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Retrieve the cached Settings singleton, or create if needed.
    """
    global _settings_instance
    if _settings_instance is None:
        raise RuntimeError("Settings not initialized")
    return _settings_instance
