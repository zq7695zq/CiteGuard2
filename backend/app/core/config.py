# 中文注释：本文件(backend/app/core/config.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://citeguard:citeguard@postgres:5432/citeguard"
    redis_url: str = "redis://redis:6379/0"
    storage_root: str = "/data/storage"
    llm_provider: str = "mock"
    openai_api_key: str | None = None
    siliconflow_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    siliconflow_model: str = "Qwen/Qwen2.5-7B-Instruct"
    zotero_snapshot_path: str = "/data/fixtures/zotero_snapshot.json"
    crossref_email: str | None = None

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
