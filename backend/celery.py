# backend/celery.py
import os
from celery import Celery
from celery.signals import task_failure

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Create Celery app
app = Celery('backend')

# Load config from Django settings with 'CELERY' namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Add worker configuration
app.conf.update(
    worker_pool='solo',  # Use solo pool for Windows/debugging
    worker_concurrency=1,
    task_always_eager=False,
    task_eager_propagates=False,
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    print(f"Task {sender.name} (ID: {task_id}) failed with exception: {exception}")