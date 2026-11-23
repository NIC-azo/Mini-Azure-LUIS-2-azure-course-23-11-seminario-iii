"""
Suite de Pruebas en Producción Cloud (Render Free HTTPS)
Mini-Azure LUIS v2
URL: https://mini-azure-luis-v2-kbos.onrender.com
"""

import json
import urllib.request
import urllib.error

BASE_URL = "https://mini-azure-luis-v2-kbos.onrender.com"

def request_api(url, method="GET", data=None, token=None):
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(text)
            except Exception:
                return resp.status, text
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8")
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text


def main():
    print("=" * 70)
    print("🌐 VALIDACIÓN DE PRODUCCIÓN EN LA NUBE (RENDER HTTPS)")
    print(f"URL Pública: {BASE_URL}")
    print("=" * 70)

    # 1. Healthcheck público
    status, res = request_api(f"{BASE_URL}/health")
    print(f"1. GET /health -> HTTP {status} (Servicio: {res.get('servicio')}, Status: {res.get('status')})")
    assert status == 200, f"Error en health: {status}"

    # 2. Petición no autenticada a ruta protegida -> 401
    status, res = request_api(f"{BASE_URL}/nlp/entender-comando", method="POST", data={"texto": "prueba sin token"})
    print(f"2. POST /nlp/entender-comando sin token -> HTTP {status} Unauthorized: {res.get('detail')}")
    assert status == 401, f"Esperaba 401, obtuve {status}"

    # 3. Login como OPERADOR
    status, op_login = request_api(f"{BASE_URL}/auth/login", method="POST", data={
        "username": "operador_ica",
        "password": "operador_pass_2026"
    })
    print(f"3. POST /auth/login (operador_ica) -> HTTP {status} OK (Rol: {op_login.get('role')})")
    assert status == 200 and op_login.get("role") == "OPERADOR"
    op_token = op_login["access_token"]

    # 4. Operación exitosa de OPERADOR -> 200
    status, cmd_res = request_api(
        f"{BASE_URL}/nlp/entender-comando",
        method="POST",
        data={"texto": "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe"},
        token=op_token
    )
    print(f"4. POST /nlp/entender-comando (OPERADOR) -> HTTP {status} OK")
    print(f"   -> Intención: {cmd_res.get('intencion')} (Confianza: {cmd_res.get('confianza_intencion')})")
    print(f"   -> Acción sugerida: {cmd_res.get('accion_sugerida')}")
    assert status == 200 and "intencion" in cmd_res

    # 5. Bloqueo de OPERADOR intentando consultar estadísticas -> 403 Forbidden
    status, rbac_res = request_api(f"{BASE_URL}/nlp/estadisticas", method="GET", token=op_token)
    print(f"5. GET /nlp/estadisticas (OPERADOR) -> HTTP {status} Forbidden: {rbac_res.get('detail')}")
    assert status == 403, f"Esperaba 403, obtuve {status}"

    # 6. Login como SUPERVISOR
    status, sup_login = request_api(f"{BASE_URL}/auth/login", method="POST", data={
        "username": "supervisor_ica",
        "password": "supervisor_pass_2026"
    })
    print(f"6. POST /auth/login (supervisor_ica) -> HTTP {status} OK (Rol: {sup_login.get('role')})")
    assert status == 200 and sup_login.get("role") == "SUPERVISOR"
    sup_token = sup_login["access_token"]

    # 7. Acceso exitoso de SUPERVISOR a estadísticas -> 200 OK
    status, stats_res = request_api(f"{BASE_URL}/nlp/estadisticas", method="GET", token=sup_token)
    print(f"7. GET /nlp/estadisticas (SUPERVISOR) -> HTTP {status} OK")
    print(f"   -> Total mensajes registrados: {stats_res.get('total_mensajes')}")
    print(f"   -> Confianza promedio: {stats_res.get('confianza_promedio')}")
    print(f"   -> Tasa de derivación: {stats_res.get('tasa_derivacion')}")
    assert status == 200 and "total_mensajes" in stats_res

    # 8. Carga de Interfaz Web Streamlit (Login Gate en /)
    status, root_html = request_api(f"{BASE_URL}/")
    print(f"8. GET / (Streamlit Web UI) -> HTTP {status} OK ({len(root_html)} bytes recibidos)")
    assert status == 200 and ("Mini-Azure LUIS" in root_html or "Streamlit" in root_html)

    print("=" * 70)
    print("🎉 TODOS LOS ESCENARIOS EN PRODUCCIÓN HTTPS RENDER FUERON VALIDADOS AL 100%")
    print("=" * 70)


if __name__ == "__main__":
    main()
