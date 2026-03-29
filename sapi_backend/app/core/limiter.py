from starlette.requests import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def upload_key_func(request: Request) -> str:
    """Key function para upload: devuelve '{role}:{ip}'.
    Permite que get_upload_limit() diferencie el límite por rol.
    """
    from app.core.security import decode_token_role

    ip = get_remote_address(request)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        role = decode_token_role(auth_header[7:])
        return f"{role}:{ip}"
    return f"user:{ip}"


def get_upload_limit(key: str) -> str:
    """Límite de upload dinámico basado en el rol codificado en la key.

    user              → 10/minute
    document_reviewer → 30/minute
    admin             → 1000/minute (sin límite práctico)
    """
    if key.startswith("admin:"):
        return "1000/minute"
    if key.startswith("document_reviewer:"):
        return "30/minute"
    return "10/minute"


limiter = Limiter(key_func=get_remote_address)
