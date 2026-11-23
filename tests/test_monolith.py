"""
Test de verificación del contenedor monolítico de Mini-Azure LUIS v2
Valida que un único puerto público ($PORT=10000) enruta correctamente:
1. /health, /auth/login y /nlp/* hacia FastAPI.
2. / hacia la interfaz web de Streamlit.
"""

import json
import urllib.request
import urllib.error

base_url = "http://localhost:10000"

def request_http(url, method="GET", data=None, token=None):
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    b = json.dumps(data).encode("utf-8") if data else None
    r = urllib.request.Request(url, data=b, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=6) as resp:
            body = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body


def main():
    print("=" * 65)
    print("🧪 PROBANDO MONOLITO EN PUERTO UNICO: http://localhost:10000")
    print("=" * 65)

    # 1. Healthcheck FastAPI
    code, res = request_http(f"{base_url}/health")
    print(f"1. GET /health -> HTTP {code}: {res.get('servicio')} (status: {res.get('status')})")
    assert code == 200 and res.get("status") == "online", "Falla en /health"

    # 2. Login FastAPI
    code, res = request_http(f"{base_url}/auth/login", method="POST", data={
        "username": "operador_ica",
        "password": "operador_pass_2026"
    })
    print(f"2. POST /auth/login -> HTTP {code}: Rol asignado = {res.get('role')}")
    assert code == 200 and res.get("role") == "OPERADOR", "Falla en login"
    op_token = res["access_token"]

    # 3. RBAC 403 Forbidden
    code, res = request_http(f"{base_url}/nlp/estadisticas", method="GET", token=op_token)
    print(f"3. GET /nlp/estadisticas con token OPERADOR -> HTTP {code}: {res.get('detail')}")
    assert code == 403, "Falla en RBAC 403"

    # 4. Streamlit Frontend en /
    code, res = request_http(f"{base_url}/")
    print(f"4. GET / (Streamlit Frontend) -> HTTP {code}: {len(res)} bytes transferidos")
    assert code == 200 and ("Mini-Azure LUIS" in res or "Streamlit" in res), "Falla en frontend Streamlit"

    print("=" * 65)
    print("🎉 TODAS LAS VERIFICACIONES DEL CONTENEDOR MONOLITICO PASARON AL 100%")
    print("=" * 65)


if __name__ == "__main__":
    main()
