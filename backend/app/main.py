import logging
import socket
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import trace
from .config import get_settings
from .database import Base, SessionLocal, engine
from .routers import auth, dashboard, demo, reports, sessions, settings, slots, users, ws
from .seed import seed

settings_ = get_settings()
logging.basicConfig(
    level=settings_.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("parking")

if settings_.demo_mode:
    trace.instrument(engine)

HOSTNAME = socket.gethostname()


def init_db(retries: int = 30, delay: float = 2.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(engine)
            break
        except OperationalError:
            if attempt == retries:
                raise
            log.warning("database not ready (attempt %d/%d), retrying", attempt, retries)
            time.sleep(delay)
    with SessionLocal() as db:
        seed(db)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings_.jwt_secret.startswith("change-me"):
        log.warning("JWT_SECRET is the default value; set a strong secret before deploying")
    init_db()
    yield


app = FastAPI(
    title="Smart Parking Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


def _start_trace(request: Request) -> dict | None:
    path = request.url.path
    if not (settings_.demo_mode and request.headers.get("x-debug-trace") == "1" and path.startswith("/api/")):
        return None
    if path.startswith("/api/demo/traces"):
        return None
    t = trace.start(request.method, path)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        trace.step(
            "edge",
            "Nginx (Public subnet) รับ request แล้ว reverse proxy เข้า Private subnet",
            f"client {forwarded} → nginx {request.client.host} → backend {HOSTNAME}:8000",
            feature="Two-tier network",
        )
    else:
        trace.step("edge", "เรียก backend ตรง (dev mode ไม่ผ่าน Nginx)", f"client {request.client.host}")
    trace.step("api", f"FastAPI รับ {request.method} {path}", f"REST API ใน private subnet (container {HOSTNAME})", feature="REST API")
    return t


@app.middleware("http")
async def access_log(request: Request, call_next):
    started = time.perf_counter()
    t = _start_trace(request)
    response = await call_next(request)
    if t is not None:
        trace.step("api", f"ตอบกลับ HTTP {response.status_code}", ok=response.status_code < 400)
        trace.finish(t, response.status_code)
        response.headers["X-Trace-Id"] = str(t["id"])
    elapsed = (time.perf_counter() - started) * 1000
    log.info("%s %s -> %d (%.0f ms)", request.method, request.url.path, response.status_code, elapsed)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = exc.errors()
    first = errors[0] if errors else {}
    message = str(first.get("msg", "ข้อมูลไม่ถูกต้อง")).removeprefix("Value error, ")
    field = ".".join(str(p) for p in first.get("loc", [])[1:])
    trace.step("logic", "Validation ไม่ผ่าน (Pydantic)", f"{field}: {message}", feature="Transaction + Validation", ok=False)
    return JSONResponse(
        status_code=422,
        content={"detail": {"message": message, "field": field, "code": "validation_error"}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    detail = exc.detail.get("message") if isinstance(exc.detail, dict) else exc.detail
    trace.step("logic", f"ปฏิเสธคำขอ ({exc.status_code})", str(detail), ok=False)
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "เกิดข้อผิดพลาดในระบบ กรุณาลองใหม่อีกครั้ง"})


@app.get("/api/health", tags=["health"])
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok"}


for r in (auth, dashboard, slots, sessions, reports, users, settings, demo, ws):
    app.include_router(r.router, prefix="/api")
