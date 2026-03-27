#!/bin/bash
export DATABASE_URL=sqlite:///./test.db
export LOCAL_STORAGE_PATH=./uploads
export REDIS_URL=redis://localhost:6379/0
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
export PYTHONPATH=.
pytest tests/ "$@"
