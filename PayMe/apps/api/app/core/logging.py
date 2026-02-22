import json
import logging
import time
import uuid
from pathlib import Path

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.settings import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.time(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra_request_id = getattr(record, "request_id", None)
        if extra_request_id:
            payload["request_id"] = extra_request_id
        return json.dumps(payload)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("payme")
    logger.setLevel(logging.INFO)
    logger.handlers = []
    formatter = JsonFormatter()

    stdout = logging.StreamHandler()
    stdout.setFormatter(formatter)
    logger.addHandler(stdout)

    log_path = Path(settings.log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


app_logger = configure_logging()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
