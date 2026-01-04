# CiteGuard2 Backend

## Development

```bash
export DATABASE_URL=postgresql+psycopg2://citeguard:citeguard@localhost:5432/citeguard
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Celery worker:

```bash
celery -A app.worker.celery_app worker -B --loglevel=info
```
