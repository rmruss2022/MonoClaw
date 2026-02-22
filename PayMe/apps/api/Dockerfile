FROM python:3.11-slim

WORKDIR /workspace/apps/api

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY apps/api /workspace/apps/api
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -e .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
