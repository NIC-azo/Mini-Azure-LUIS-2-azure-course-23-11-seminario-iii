"""
Módulo de Seguridad, Autenticación JWT y Control de Acceso Basado en Roles (RBAC)
para Mini-Azure LUIS v2.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    OPERADOR_USER,
    OPERADOR_PASS,
    SUPERVISOR_USER,
    SUPERVISOR_PASS,
)

# Esquema Bearer de FastAPI (auto_error=False para controlar manualmente las excepciones 401)
bearer_scheme = HTTPBearer(auto_error=False)


def authenticate_user(username: str, password: str) -> Optional[Dict[str, str]]:
    """
    Valida las credenciales contra las variables de entorno del sistema.
    Retorna diccionario con username y rol correspondiente, o None si son inválidas.
    """
    if username == OPERADOR_USER and password == OPERADOR_PASS:
        return {"username": username, "role": "OPERADOR"}
    if username == SUPERVISOR_USER and password == SUPERVISOR_PASS:
        return {"username": username, "role": "SUPERVISOR"}
    return None


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Genera un token JWT firmado con HS256 conteniendo el identificador de usuario (sub) y su rol.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "iat": now,
        "exp": expire,
    })
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    """
    Dependencia FastAPI que extrae y valida el token Bearer del header Authorization.
    Lanza HTTP 401 si el token no existe, está expirado o tiene firma inválida.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado o token ausente. Proporcione header 'Authorization: Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if not username or not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: payload incompleto",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"username": username, "role": role}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado. Inicie sesión nuevamente en /auth/login",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado o token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(allowed_roles: List[str]):
    """
    Fábrica de dependencias RBAC.
    Verifica que el rol del usuario autenticado se encuentre dentro de allowed_roles.
    Lanza HTTP 403 Forbidden si el rol no tiene los permisos suficientes.
    """
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: permisos insuficientes para el rol {user_role}. Requiere uno de: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker
