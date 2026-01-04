# 中文注释：本文件(backend/app/tools/errors.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
from typing import Any


class ToolError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False, retry_after_ms: int | None = None, details: Any | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_after_ms = retry_after_ms
        self.details = details

    def to_dict(self) -> dict:
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
                "retry_after_ms": self.retry_after_ms,
                "details": self.details,
            },
        }
