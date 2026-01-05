import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "CiteGuard API"
    API_V1_STR: str = "/api/v1"
    
    # SiliconFlow API
    SILICONFLOW_API_KEY: str = os.getenv("SILICONFLOW_API_KEY", "sk-dwxsrbmfmsjemoazxuodmnjtlbspvijxdvdlsqrpeiaekakq")
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_MODEL: str = "deepseek-ai/DeepSeek-V3.2"

    # CrossRef API
    CROSSREF_API_URL: str = "https://api.crossref.org/works"
    CROSSREF_EMAIL: str = os.getenv("CROSSREF_EMAIL", "ayanami1999@qq.com")

    # Semantic Scholar API
    SEMANTIC_SCHOLAR_API_URL: str = "https://api.semanticscholar.org/graph/v1/paper"
    SEMANTIC_SCHOLAR_API_KEY: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

    # Database & Celery
    # Using SQLite for both DB and Broker for portability as per plan
    DATABASE_URL: str = "sqlite:///./citeguard.db"
    CELERY_BROKER_URL: str = "sqla+sqlite:///./celery_broker.db"
    CELERY_RESULT_BACKEND: str = "db+sqlite:///./celery_results.db"

    class Config:
        case_sensitive = True

settings = Settings()
