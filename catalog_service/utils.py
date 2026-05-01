import logging
import json
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from prometheus_client import make_asgi_app

class JSONLogFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name
        }
        # Masking sensitive data naively for assignment purposes
        msg_lower = log_record["message"].lower()
        if "email" in msg_lower or "@" in msg_lower:
             log_record["message"] = "[MASKED_SENSITIVE_DATA]"
        if "phone" in msg_lower or "mobile" in msg_lower:
             log_record["message"] = "[MASKED_SENSITIVE_DATA]"
             
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    for handler in logger.handlers:
        logger.removeHandler(handler)
    logHandler = logging.StreamHandler()
    formatter = JSONLogFormatter()
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)
    return logger

def setup_common_app(app):
    setup_logging()
    
    # Add prometheus metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    
    @app.middleware("http")
    async def add_correlation_id(request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.status_code,
                    "message": exc.detail,
                    "correlationId": correlation_id
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": 422,
                    "message": str(exc.errors()),
                    "correlationId": correlation_id
                }
            }
        )

    @app.get("/health")
    def health_check():
        return {"status": "ok"}
