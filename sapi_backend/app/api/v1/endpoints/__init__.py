from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.documents import router as documents_router

__all__ = ["auth_router", "users_router", "documents_router"]
