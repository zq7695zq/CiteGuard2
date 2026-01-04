# CiteGuard2 引文核查 Agent 平台（v2）

本项目提供前后端分离、可断续/可恢复的引文核查 Agent 平台，支持 SSE 实时事件、任务级别容错与恢复、OpenAI + SiliconFlow 多 LLM Provider、以及结构化学术工具（本地 Zotero + Crossref）。

## 目录结构

```
repo/
  backend/          # FastAPI API + Celery worker + 任务编排
  frontend/         # React + Vite 前端
  fixtures/         # 最小可用 demo 样例
  docker-compose.yml
```

## 依赖与环境

- Python 3.11+
- Node.js 20+
- Docker / Docker Compose（推荐）

## 配置说明（环境变量）

后端支持以下环境变量：

- `DATABASE_URL`：数据库连接串（Postgres）
- `REDIS_URL`：Redis 连接串
- `STORAGE_ROOT`：本地存储根目录（用于 artifacts/intermediate）
- `LLM_PROVIDER`：`openai` / `siliconflow` / `mock`
- `OPENAI_API_KEY`：OpenAI Key（仅 `openai` 时需要）
- `SILICONFLOW_API_KEY`：SiliconFlow Key（仅 `siliconflow` 时需要）
- `OPENAI_MODEL` / `SILICONFLOW_MODEL`：模型名称
- `ZOTERO_SNAPSHOT_PATH`：Zotero 快照 JSON 路径
- `CROSSREF_EMAIL`：Crossref 友好邮件（可选）

> **注意**：禁止普通网页搜索，外部信息仅来自结构化工具（Zotero Snapshot + Crossref）。

## 方式一：Docker Compose 一键启动（推荐）

```bash
docker-compose up --build
```

- 后端 API：`http://localhost:8000`
- 前端：`http://localhost:5173`

### 数据库迁移

容器启动后执行一次：

```bash
docker-compose exec backend alembic upgrade head
```

## 方式二：本地运行（不使用 Docker）

### 1) 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgresql+psycopg2://citeguard:citeguard@localhost:5432/citeguard
export REDIS_URL=redis://localhost:6379/0
export STORAGE_ROOT=./data/storage
export ZOTERO_SNAPSHOT_PATH=../fixtures/zotero_snapshot.json
export LLM_PROVIDER=mock

alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2) Worker

```bash
cd backend
source .venv/bin/activate
celery -A app.worker.celery_app worker -B --loglevel=info
```

### 3) 前端

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## Demo（最小可用样例）

本地 SQLite + mock LLM 演示：

```bash
cd backend
python -m app.demo.run_demo
```

运行后可在 `demo_storage/jobs/<job_id>/artifacts/` 获取：

- `existence_report.json`
- `context_report.json`
- `fixed.bib`

## API 概览

- `POST /jobs`：创建任务
- `GET /jobs/{job_id}`：查询任务状态
- `GET /jobs/{job_id}/events`：SSE 事件流
- `GET /jobs/{job_id}/tasks`：任务列表
- `POST /jobs/{job_id}/pause|resume|cancel|retry|skip`
- `GET /jobs/{job_id}/artifacts` / `GET /jobs/{job_id}/artifacts/{name}`

## 前端功能

- 任务列表 / 详情页面
- 实时事件流（SSE）
- 任务重试 / 跳过 / 暂停 / 继续 / 取消
- 可视化进度与错误信息

## 注意事项

- 任何外部信息获取必须通过结构化工具（Zotero + Crossref），禁止网页搜索。
- 任务幂等：`(job_id, type, key)` 唯一约束，重复执行覆盖自身结果。
