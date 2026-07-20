#!/usr/bin/env bash

# run on local development to start the server the celery and the minio server simultaneously

echo "[+] Starting all Processes..."

echo "Starting the local server..."
py manage.py runserver &


echo "Starting the background celery worker..."
celery -A EdPal worker --loglevel=info --pool=solo -E &

echo "Start celery beat for scheduled workers..."
celery -A EdPal beat --loglevel=info &

echo "Start celery flower..."
celery -A EdPal flower &

# running from the dir of the minio server ie C:\minio
echo "Starting the minio server..."
C:\\minio\\minio.exe server C:\\minio\\data --license C:\\minio\\minio.license &

wait

echo "All processes have been started. Press Ctrl+C to stop."