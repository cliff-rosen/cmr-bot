from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, llm, search, web_retrieval, general_chat, conversations, memories, assets, profile, workflow
from database import init_db
from config import settings, setup_logging
from middleware import LoggingMiddleware
from pydantic import ValidationError
from starlette.responses import JSONResponse
from services.chat_payloads import register_builtin_tools

# Setup logging first
logger, request_id_filter = setup_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.SETTING_VERSION,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
        "defaultModelsExpandDepth": -1,
    }
)

# Add logging middleware
app.add_middleware(LoggingMiddleware, request_id_filter=request_id_filter)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
    expose_headers=settings.CORS_EXPOSE_HEADERS,
)

# Include routers
logger.info("Including routers...")

# Auth router
app.include_router(
    auth.router,
    prefix="/api/auth",
    tags=["auth"],
    responses={401: {"description": "Not authenticated"}}
)

# Core API routers
app.include_router(llm.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(web_retrieval.router, prefix="/api")
app.include_router(general_chat.router)
app.include_router(conversations.router)
app.include_router(memories.router)
app.include_router(assets.router)
app.include_router(profile.router)
app.include_router(workflow.router)

logger.info("Routers included")


@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")
    init_db()
    logger.info("Database initialized")
    register_builtin_tools()
    logger.info("Chat tools registered")


@app.get("/")
async def root():
    """Root endpoint - redirects to API health check"""
    return {"message": "CMR-Bot API", "health": "/api/health", "docs": "/docs"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "version": settings.SETTING_VERSION}


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    logger.error(f"Validation error in {request.url.path}:")
    for error in exc.errors():
        logger.error(f"  - {error['loc']}: {error['msg']} (type: {error['type']})")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )


logger.info("Application startup complete")
