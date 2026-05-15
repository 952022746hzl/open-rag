from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_PRIVATE_KEY_PATH: str = "keys/private.pem"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 7200
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    INIT_ADMIN_USERNAME: str = "admin"
    INIT_ADMIN_PASSWORD: str

    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "factory-documents"

    OPENAI_API_KEY: str
    OPENAI_API_URL: str = "https://api.openai.com/v1"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "factory_chunks"


settings = Settings()
