from celery import Celery

from app.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "document_automation",
    broker=settings.rabbitmq_url,
    backend=None,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_soft_time_limit=settings.bda_poll_max_seconds,
    task_time_limit=settings.bda_poll_max_seconds + 60,
    broker_connection_retry_on_startup=True,
)
