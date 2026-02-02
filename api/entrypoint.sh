#!/bin/bash

# Configure Jackett Indexers
if [ ! -d "/app/jackett" ]; then
    echo "Jackett directory not found, extracting from tar file..."
    if [ -f "/app/jackett.tar" ]; then
        tar -xf jackett.tar
        echo "Extraction complete."
    else
        echo "Error: jackett.tar not found!"
        exit 1
    fi
fi

# Start Celery Worker
celery -A celery_worker worker -Q transcoding --concurrency=$CELERY_NUM_WORKERS --loglevel=info -E &

# Start API Server
if [ "$API_DEBUG" = "True" ]; then
    echo "Running Development Server"
    uvicorn main:app --reload --host 0.0.0.0 --port 8080
else
    echo "Running Production Server"
    uvicorn main:app --host 0.0.0.0 --port 8080
fi