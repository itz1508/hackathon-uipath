"""Worker with undeclared deps."""

import celery
import redis

def run_task():
    return celery.current_app
