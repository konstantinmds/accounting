from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    S3_ENDPOINT: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None

    # App
    APP_NAME: str = "BH KB API"
    APP_ENV: str = "dev"


    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
