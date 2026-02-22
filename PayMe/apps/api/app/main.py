from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.matching import claims_router
from app.api.routes.matching import router as matching_router
from app.api.routes.matching import settlement_router
from app.api.routes.me import router as me_router
from app.api.routes.onboarding import router as onboarding_router
from app.core.logging import RequestIDMiddleware, app_logger

app = FastAPI(title="PayMe Lite API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:15173",
        "http://127.0.0.1:15173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(onboarding_router)
app.include_router(matching_router)
app.include_router(settlement_router)
app.include_router(claims_router)
app.include_router(integrations_router)
app.include_router(admin_router)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    app_logger.info(
        "request_completed",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
        },
    )
    return response
