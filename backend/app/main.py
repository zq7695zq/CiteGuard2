# 中文注释：本文件(backend/app/main.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import jobs, events

app = FastAPI(title="CiteGuard2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(events.router)
