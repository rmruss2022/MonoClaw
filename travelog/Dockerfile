# Travelog — stdlib Python web app. ffmpeg is optional (voice-note transcode).
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY server.py icon.svg icon.png icon-192.png icon-512.png ./

# Railway injects $PORT; bind all interfaces; keep db + media on the volume.
ENV TRAVELOG_HOST=0.0.0.0 \
    TRAVELOG_DATA=/data \
    PYTHONUNBUFFERED=1


CMD ["python3", "server.py"]
