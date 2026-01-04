# 中文注释：本文件(backend/app/storage/fs.py)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
from __future__ import annotations
import hashlib
from pathlib import Path
from app.core.config import get_settings


class Storage:
    def __init__(self) -> None:
        settings = get_settings()
        self.root = Path(settings.storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_text(self, relative_path: str, data: str) -> str:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return str(path)

    def write_json(self, relative_path: str, data: str) -> str:
        return self.write_text(relative_path, data)

    def read_text(self, relative_path: str) -> str:
        return (self.root / relative_path).read_text(encoding="utf-8")

    def read_uri(self, uri: str) -> str:
        path = Path(self.from_uri(uri))
        return path.read_text(encoding="utf-8")

    def compute_sha256(self, relative_path: str) -> str:
        path = self.root / relative_path
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return digest

    def to_uri(self, relative_path: str) -> str:
        return f"file://{self.root / relative_path}"

    def from_uri(self, uri: str) -> str:
        if uri.startswith("file://"):
            return uri.replace("file://", "")
        return uri
