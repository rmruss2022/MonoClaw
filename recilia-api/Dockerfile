# Recilia API — zero-dependency Python stdlib service. Tiny, reboot-safe.
FROM python:3.12-slim

WORKDIR /app
COPY . /app

# Railway injects $PORT. Bind all interfaces; keep SQLite on a mounted volume at
# /data so accounts + grove sync survive redeploys.
ENV RECILIA_HOST=0.0.0.0 \
    RECILIA_DATA=/data \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data

EXPOSE 8080
CMD ["python3", "server.py"]
