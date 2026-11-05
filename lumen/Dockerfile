# Lumen — zero-dependency Python stdlib web app. Tiny, reboot-safe image.
FROM python:3.12-slim

WORKDIR /app
COPY . /app

# Railway (and most PaaS) inject $PORT; the server reads it. Bind on all interfaces,
# and keep the SQLite DB on a mounted volume at /data so accounts survive redeploys.
ENV LUMEN_HOST=0.0.0.0 \
    LUMEN_DATA=/data \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data

EXPOSE 8080
CMD ["python3", "server.py"]
