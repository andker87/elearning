from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Microsoft Graph (Teams attendance) - opzionale, fallback manuale se assenti
    GRAPH_TENANT_ID: Optional[str] = None
    GRAPH_CLIENT_ID: Optional[str] = None
    GRAPH_CLIENT_SECRET: Optional[str] = None

    @property
    def graph_enabled(self) -> bool:
        return bool(self.GRAPH_TENANT_ID and self.GRAPH_CLIENT_ID and self.GRAPH_CLIENT_SECRET)

settings = Settings()
