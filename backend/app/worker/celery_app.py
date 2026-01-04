# 中文注释：本文件(backend/app/worker/celery_app.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "citeguard",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_track_started=True,
    beat_schedule={
        "watchdog": {
            "task": "app.worker.tasks.watchdog_tick",
            "schedule": 10.0,
        }
    },
)
