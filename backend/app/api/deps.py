# 中文注释：本文件(backend/app/api/deps.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from app.db.session import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
