from celery import Celery
from .config import settings

celery_app = Celery(
    "citeguard",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.tasks']
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    # Retry policy
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Optional: Route specific tasks if needed
# celery_app.conf.task_routes = {
#     "app.tasks.verify_citation": "verification_queue",
# }
