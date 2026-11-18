from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router
from backend.app.config import get_settings
from backend.app.database import init_db
from backend.app.auth import seed_demo_users


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Gemini Support Agent API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)
    return application


app = create_app()


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_demo_users()
