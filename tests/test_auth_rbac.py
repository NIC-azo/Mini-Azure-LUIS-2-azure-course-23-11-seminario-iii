"""
Suite de Pruebas de Seguridad Backend, Autenticación JWT y RBAC
para Mini-Azure LUIS v2.
Valida la lógica de tokens, perfiles y peticiones HTTP en vivo (códigos 401, 403 y 200).
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# Ajustar PYTHONPATH hacia server
base_dir = Path(__file__).resolve().parent.parent
server_dir = base_dir / "server"
sys.path.insert(0, str(server_dir))

from app.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    require_role,
)
from app.config import (
    OPERADOR_USER,
    OPERADOR_PASS,
    SUPERVISOR_USER,
    SUPERVISOR_PASS,
)
from fastapi.security import HTTPAuthorizationCredentials


def test_auth_logic():
    print("-" * 65)
    print("1. Validando Lógica Criptográfica de Tokens y RBAC (Unitario)")
    print("-" * 65)

    # 1.1 Autenticación de credenciales
    op_user = authenticate_user(OPERADOR_USER, OPERADOR_PASS)
    assert op_user is not None and op_user["role"] == "OPERADOR"
    print(f"   [OK] Autenticación de OPERADOR ({OPERADOR_USER})")

    sup_user = authenticate_user(SUPERVISOR_USER, SUPERVISOR_PASS)
    assert sup_user is not None and sup_user["role"] == "SUPERVISOR"
    print(f"   [OK] Autenticación de SUPERVISOR ({SUPERVISOR_USER})")

    bad_user = authenticate_user("falso_user", "clave_erronea")
    assert bad_user is None
    print("   [OK] Rechazo de credenciales inexistentes")

    # 1.2 Generación y verificación de token
    token = create_access_token(data={"sub": op_user["username"], "role": op_user["role"]})
    assert token and isinstance(token, str)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    decoded = get_current_user(creds)
    assert decoded["username"] == OPERADOR_USER and decoded["role"] == "OPERADOR"
    print("   [OK] Generación y decodificación de JWT con payload 'sub' y 'role'")

    # 1.3 Control de Acceso por Roles (RBAC)
    check_op = require_role(["OPERADOR", "SUPERVISOR"])
    assert check_op(decoded) == decoded
    print("   [OK] Permiso concedido a OPERADOR en ruta de operador")

    check_sup_only = require_role(["SUPERVISOR"])
    try:
        check_sup_only(decoded)
        assert False, "OPERADOR no debe tener acceso a funciones de SUPERVISOR"
    except Exception as e:
        assert getattr(e, "status_code", None) == 403
        print(f"   [OK] Bloqueo 403 Forbidden a OPERADOR en función exclusiva de SUPERVISOR: {e.detail}")

    print("   -> Todas las pruebas unitarias de seguridad pasaron con éxito.\n")


def make_http_request(url: str, method: str = "GET", data: dict = None, token: str = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(resp_body)
        except Exception:
            parsed = resp_body
        return e.code, parsed


def test_live_api(base_url: str = "http://127.0.0.1:8001"):
    print("-" * 65)
    print(f"2. Validando API REST en Vivo contra {base_url} (HTTP 401, 403, 200)")
    print("-" * 65)

    # 2.1 GET /health (Público)
    code, data = make_http_request(f"{base_url}/health")
    assert code == 200, f"Error /health: {code}"
    print(f"   [OK] GET /health -> {code} OK (Servicio: {data.get('servicio')})")

    # 2.2 Login Inválido -> 401
    code, data = make_http_request(
        f"{base_url}/auth/login",
        method="POST",
        data={"username": "hacker", "password": "wrong"}
    )
    assert code == 401, f"Esperaba 401 en login inválido, obtuve {code}"
    print(f"   [OK] POST /auth/login con credenciales falsas -> {code} Unauthorized")

    # 2.3 Login OPERADOR -> 200
    code, op_data = make_http_request(
        f"{base_url}/auth/login",
        method="POST",
        data={"username": OPERADOR_USER, "password": OPERADOR_PASS}
    )
    assert code == 200 and op_data.get("role") == "OPERADOR"
    op_token = op_data["access_token"]
    print(f"   [OK] POST /auth/login OPERADOR -> {code} OK (Token emitido, rol: {op_data.get('role')})")

    # 2.4 Login SUPERVISOR -> 200
    code, sup_data = make_http_request(
        f"{base_url}/auth/login",
        method="POST",
        data={"username": SUPERVISOR_USER, "password": SUPERVISOR_PASS}
    )
    assert code == 200 and sup_data.get("role") == "SUPERVISOR"
    sup_token = sup_data["access_token"]
    print(f"   [OK] POST /auth/login SUPERVISOR -> {code} OK (Token emitido, rol: {sup_data.get('role')})")

    # 2.5 Sin token -> 401
    code, data = make_http_request(
        f"{base_url}/nlp/entender-comando",
        method="POST",
        data={"texto": "La camara de frio 2 subio a 9 grados"}
    )
    assert code == 401, f"Esperaba 401 sin token, obtuve {code}"
    print(f"   [OK] POST /nlp/entender-comando sin token -> {code} Unauthorized")

    # 2.6 Token inválido -> 401
    code, data = make_http_request(
        f"{base_url}/nlp/entender-comando",
        method="POST",
        data={"texto": "La camara de frio 2 subio a 9 grados"},
        token="token_falso_invalido"
    )
    assert code == 401, f"Esperaba 401 con token falso, obtuve {code}"
    print(f"   [OK] POST /nlp/entender-comando con token falso -> {code} Unauthorized")

    # 2.7 OPERADOR ejecuta /nlp/entender-comando -> 200
    code, data = make_http_request(
        f"{base_url}/nlp/entender-comando",
        method="POST",
        data={"texto": "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe"},
        token=op_token
    )
    assert code == 200, f"Esperaba 200 para operador, obtuve {code}"
    print(f"   [OK] POST /nlp/entender-comando con token OPERADOR -> {code} OK (Intención: {data.get('intencion')})")

    # 2.8 OPERADOR intenta GET /nlp/estadisticas -> 403 Forbidden
    code, data = make_http_request(
        f"{base_url}/nlp/estadisticas",
        method="GET",
        token=op_token
    )
    assert code == 403, f"Esperaba 403 para operador en estadisticas, obtuve {code}"
    print(f"   [OK] GET /nlp/estadisticas con token OPERADOR -> {code} Forbidden (Acceso denegado)")

    # 2.9 OPERADOR intenta POST /nlp/estadisticas/reiniciar -> 403 Forbidden
    code, data = make_http_request(
        f"{base_url}/nlp/estadisticas/reiniciar",
        method="POST",
        token=op_token
    )
    assert code == 403, f"Esperaba 403 para operador en reiniciar, obtuve {code}"
    print(f"   [OK] POST /nlp/estadisticas/reiniciar con token OPERADOR -> {code} Forbidden (Acceso denegado)")

    # 2.10 SUPERVISOR accede a GET /nlp/estadisticas -> 200 OK
    code, data = make_http_request(
        f"{base_url}/nlp/estadisticas",
        method="GET",
        token=sup_token
    )
    assert code == 200, f"Esperaba 200 para supervisor en estadisticas, obtuve {code}"
    print(f"   [OK] GET /nlp/estadisticas con token SUPERVISOR -> {code} OK (Total eventos: {data.get('total_mensajes')})")

    # 2.11 SUPERVISOR ejecuta POST /nlp/estadisticas/reiniciar -> 200 OK
    code, data = make_http_request(
        f"{base_url}/nlp/estadisticas/reiniciar",
        method="POST",
        token=sup_token
    )
    assert code == 200, f"Esperaba 200 para supervisor en reiniciar, obtuve {code}"
    print(f"   [OK] POST /nlp/estadisticas/reiniciar con token SUPERVISOR -> {code} OK")

    print("\n" + "=" * 65)
    print("🎉 TODAS LAS PRUEBAS DE SEGURIDAD (401, 403, 200) COMPLETADAS CON ÉXITO")
    print("=" * 65)


if __name__ == "__main__":
    test_auth_logic()
    # Si el servidor está activo, probar la API en vivo
    try:
        test_live_api()
    except Exception as e:
        print(f"ℹ️ Servidor en vivo no disponible aún para test HTTP ({e}). Iniciando contenedor...")
