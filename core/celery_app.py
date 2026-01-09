from celery import Celery
from core.env_config import REDIS_URL

celery = Celery(
    "tournaments",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Africa/Lagos',
    enable_utc=True,
)
