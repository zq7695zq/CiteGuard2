# 中文注释：本文件(backend/app/db/session.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
