"""
Configurações globais da aplicação utilizando Pydantic Settings.
Carrega variáveis de ambiente a partir do arquivo .env.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    DATABASE_PATH: str = "aurora.db"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_file_path(self) -> Path:
        path = Path(self.DATABASE_PATH)
        if not path.is_absolute():
            return PROJECT_ROOT / path
        return path


settings = Settings()
