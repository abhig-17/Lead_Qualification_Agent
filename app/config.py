import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL", "")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./leads.db")
    
    # Scoring Config
    FIT_WEIGHT: float = 0.45
    INTENT_WEIGHT: float = 0.55
    
    # Tier Cutoffs
    HOT_THRESHOLD: int = 75
    WARM_THRESHOLD: int = 50
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
