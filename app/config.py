from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URL: str
    SECRET_KEY: str
    DB_NAME: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    LANGUAGE: str = "en_US" # Default language

    class Config:
        env_file = ".env"

settings = Settings()