from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Передаем абсолютный путь к .env напрямую в конфигурацию
    model_config = SettingsConfigDict(
        extra='ignore',
        env_file=Path(__file__).resolve().parent.parent.parent / '.env'
    )
    print(model_config)
settings = Settings()