import sys
from pathlib import Path
import json
import time
from datetime import datetime
import pandas as pd
import requests
import streamlit as st

# Inyectar directorios en sys.path para resolver 'app' tanto en contenedor como en local
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
for p in [str(PROJECT_ROOT), str(CURRENT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Cargar configuración del cliente de forma robusta e inmune a colisiones de sys.path
import importlib.util
client_cfg_file = CURRENT_DIR / "config.py"
if client_cfg_file.exists():
    spec = importlib.util.spec_from_file_location("client_config_module", str(client_cfg_file))
    client_cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client_cfg)
    TARGET_SERVER_IP = getattr(client_cfg, "TARGET_SERVER_IP", "127.0.0.1")
    SERVER_PORT = getattr(client_cfg, "SERVER_PORT", "8001")
    API_PUBLIC_URL = getattr(client_cfg, "API_PUBLIC_URL", "")
    get_api_base_url = getattr(client_cfg, "get_api_base_url", lambda *args, **kwargs: "http://127.0.0.1:8001")
else:
    try:
        from app.config import TARGET_SERVER_IP, SERVER_PORT, API_PUBLIC_URL, get_api_base_url
    except Exception:
        from config import TARGET_SERVER_IP, SERVER_PORT, API_PUBLIC_URL, get_api_base_url

# ====================================================================
# Configuración de Página y Estilos Visuales
# ====================================================================
st.set_page_config(
    page_title="Mini-Azure LUIS v2",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #38BDF8;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 0.98rem;
        color: #94A3B8;
        margin-bottom: 1.2rem;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.85), rgba(15, 23, 42, 0.95)) !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
    }
    div[data-testid="stMetric"] label, div[data-testid="stMetric"] div[data-testid="stMetricLabel"] p {
        color: #94A3B8 !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #38BDF8 !important;
        font-size: 1.85rem !important;
        font-weight: 700 !important;
    }
    .badge-op {
        background-color: rgba(59, 130, 246, 0.2);
        color: #93C5FD;
        border: 1px solid #3B82F6;
        padding: 4px 12px;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-sup {
        background-color: rgba(16, 185, 129, 0.2);
        color: #6EE7B7;
        border: 1px solid #10B981;
        padding: 4px 12px;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-action {
        background-color: rgba(245, 158, 11, 0.2);
        color: #FCD34D;
        border: 1px solid #F59E0B;
        padding: 5px 12px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.95rem;
    }
    .login-box {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.98));
        border: 1px solid rgba(56, 189, 248, 0.35);
        border-radius: 16px;
        padding: 30px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ====================================================================
# Inicialización de Sesión JWT en st.session_state
# ====================================================================
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None
if "api_url_custom" not in st.session_state:
    st.session_state.api_url_custom = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": "👋 Hola, escribe tu reporte operativo de campo (cámaras de frío, fajas, stock o despachos):",
        }
    ]

# ====================================================================
# Configuración y Resolución de URL del Backend
# ====================================================================
API_BASE = get_api_base_url(st.session_state.api_url_custom)

# Helper para Peticiones HTTP con Bearer Token y Manejo de Errores 401 / 403
def api_request(method: str, endpoint: str, json_data: dict = None, timeout: int = 8) -> tuple[int, any]:
    """
    Envía una petición al backend adjuntando automáticamente el token Bearer en el header.
    Si el token ha expirado (401), cierra la sesión automáticamente.
    """
    url = f"{API_BASE}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if st.session_state.access_token:
        headers["Authorization"] = f"Bearer {st.session_state.access_token}"

    try:
        resp = requests.request(method=method, url=url, json=json_data, headers=headers, timeout=timeout)
        try:
            payload = resp.json()
        except Exception:
            payload = resp.text

        # Si el backend rechaza por token expirado, forzar cierre de sesión
        if resp.status_code == 401 and st.session_state.access_token is not None:
            st.session_state.access_token = None
            st.session_state.username = None
            st.session_state.role = None
            st.warning("⚠️ Sesión expirada o token revocado. Por favor ingresa nuevamente.")
            st.rerun()

        return resp.status_code, payload
    except Exception as ex:
        return 0, str(ex)

# ====================================================================
# Verificación de Conectividad con /health (Endpoint Público)
# ====================================================================
server_online = False
server_info = {}
try:
    health_resp = requests.get(f"{API_BASE}/health", timeout=2.5)
    if health_resp.status_code == 200:
        server_online = True
        server_info = health_resp.json()
except Exception:
    pass

# ====================================================================
# Barra Lateral (Sidebar)
# ====================================================================
st.sidebar.markdown("# 🌾 Mini-Azure LUIS v2")
st.sidebar.caption("Motor Cloud NLP &bull; Agroexportación Ica")

# Estado de Conexión
if server_online:
    st.sidebar.success(f"🟢 Servidor Conectado ({server_info.get('version', '2.0.0')})")
else:
    st.sidebar.error("🔴 Servidor Inaccesible")

# Ajuste de URL de API
with st.sidebar.expander("⚙️ Conexión de Red / URL API", expanded=False):
    st.caption("Configura el endpoint del servidor (Render HTTPS o LAN):")
    nuevo_url = st.text_input("URL Backend", value=API_BASE, key="input_api_url")
    if st.button("Aplicar URL", use_container_width=True):
        st.session_state.api_url_custom = nuevo_url.strip()
        st.rerun()

# Si hay sesión iniciada, mostrar tarjeta de usuario y botón de cerrar sesión
if st.session_state.access_token is not None:
    st.sidebar.divider()
    st.sidebar.markdown("### 👤 Sesión Activa")
    st.sidebar.write(f"**Usuario:** `{st.session_state.username}`")
    if st.session_state.role == "OPERADOR":
        st.sidebar.markdown('<span class="badge-op">👷 ROL: OPERADOR</span>', unsafe_allow_html=True)
        st.sidebar.caption("Acceso exclusivo a envío de reportes operativos de campo.")
    else:
        st.sidebar.markdown('<span class="badge-sup">🛡️ ROL: SUPERVISOR</span>', unsafe_allow_html=True)
        st.sidebar.caption("Acceso completo a KPIs, bitácora y reinicio de métricas.")

    st.sidebar.write("")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
        st.session_state.access_token = None
        st.session_state.username = None
        st.session_state.role = None
        st.rerun()

st.sidebar.divider()

# ====================================================================
# Formateador Conversacional Humano para Operarios
# ====================================================================
def formatear_respuesta_humana(data: dict) -> str:
    accion = data.get("accion_sugerida", "DERIVAR_A_SUPERVISOR")
    entidades = data.get("entidades", {})

    detalles = []
    if entidades.get("AREA"):
        detalles.append(f"📍 **Ubicación:** {', '.join(entidades['AREA'])}")
    if entidades.get("PRODUCTO"):
        detalles.append(f"🍇 **Producto:** {', '.join(entidades['PRODUCTO'])}")
    if entidades.get("CANTIDAD"):
        detalles.append(f"📦 **Cantidad:** {', '.join(entidades['CANTIDAD'])}")
    if entidades.get("CODIGO_LOTE"):
        detalles.append(f"🏷️ **Lote:** {', '.join(entidades['CODIGO_LOTE'])}")

    bloque_detalles = ("\n\n" + "\n".join(detalles)) if detalles else ""

    if accion == "ALERTA_CRITICA_CALIDAD":
        return f"🚨 **Alerta de Calidad Notificada**\n\nIncidencia registrada. Se emitió alerta prioritaria a Control de Calidad y Supervisión.{bloque_detalles}"
    elif accion == "ORDEN_MANTENIMIENTO_URGENTE":
        return f"🛠️ **Orden de Mantenimiento Emitida**\n\nSolicitud técnica generada para inspección urgente de equipo.{bloque_detalles}"
    elif accion == "CONSULTAR_ERP_ALMACEN":
        return f"📋 **Consulta de Inventario Recibida**\n\nSolicitud enviada a bodega para verificar disponibilidad de stock.{bloque_detalles}"
    elif accion == "PROGRAMAR_LOGISTICA_SALIDA":
        return f"🚛 **Despacho Registrado**\n\nIniciada coordinación de transporte y documentación para salida.{bloque_detalles}"
    elif accion == "REGISTRAR_CONTROL_CALIDAD":
        return f"✅ **Control Conforme**\n\nLote aprobado en inspección sin observaciones.{bloque_detalles}"
    else:
        return f"⚠️ **Reporte Recibido y Derivado**\n\nMensaje derivado a supervisor de turno para atención operativa.{bloque_detalles}"


# ====================================================================
# PANTALLA 1: LOGIN GATE (Si no hay sesión autenticada)
# ====================================================================
if st.session_state.access_token is None:
    c_izq, c_centro, c_der = st.columns([1, 2, 1])

    with c_centro:
        st.markdown(
            """
            <div class="login-box">
                <h2 style="color: #38BDF8; margin-top: 0; text-align: center;">🌾 Mini-Azure LUIS v2</h2>
                <p style="color: #94A3B8; text-align: center; margin-bottom: 22px;">
                    Control de Acceso Basado en Roles (RBAC) &bull; Agroexportación Ica
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")

        with st.form("login_form"):
            st.markdown("#### 🔐 Iniciar Sesión")
            user_input = st.text_input("Usuario", placeholder="operador_ica o supervisor_ica")
            pass_input = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submit_login = st.form_submit_button("Ingresar al Sistema", use_container_width=True, type="primary")

            if submit_login:
                if not user_input.strip() or not pass_input.strip():
                    st.warning("⚠️ Ingrese su usuario y contraseña.")
                else:
                    with st.spinner("Autenticando credenciales..."):
                        status_c, resp_data = api_request(
                            "POST",
                            "/auth/login",
                            {"username": user_input.strip(), "password": pass_input.strip()},
                        )
                        if status_c == 200:
                            st.session_state.access_token = resp_data["access_token"]
                            st.session_state.username = resp_data["username"]
                            st.session_state.role = resp_data["role"]
                            st.success(f"✅ Bienvenido, {resp_data['username']} ({resp_data['role']})")
                            time.sleep(0.4)
                            st.rerun()
                        elif status_c == 401:
                            st.error("❌ Credenciales inválidas. Verifica tu usuario y contraseña.")
                        else:
                            st.error(f"Error al conectar con la API ({status_c}): {resp_data}")

        with st.expander("ℹ️ Credenciales de Demostración para Evaluación", expanded=True):
            st.markdown(
                """
                - **👷 Perfil OPERADOR:**
                  - Usuario: `operador_ica`
                  - Contraseña: `operador_pass_2026`
                  - *Permisos:* Emisión de reportes operativos (`/nlp/entender-comando`). Bloqueado en KPIs (`403 Forbidden`).
                - **🛡️ Perfil SUPERVISOR:**
                  - Usuario: `supervisor_ica`
                  - Contraseña: `supervisor_pass_2026`
                  - *Permisos:* Acceso total a Dashboard analítico, KPIs, bitácora y reinicio de estadísticas.
                """
            )

    st.stop()


# ====================================================================
# PANTALLA 2: VISTA ROL == OPERADOR
# ====================================================================
if st.session_state.role == "OPERADOR":
    st.markdown('<div class="main-title">👷 Terminal Operativa de Campo — Envío de Reportes</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-title">Sesión activa como <b>{st.session_state.username}</b> &bull; Fundo / Packing / Frío (Ica: Uva de Mesa y Espárragos)</div>',
        unsafe_allow_html=True,
    )

    if not server_online:
        st.error("🔴 Servidor NLP fuera de línea. Verifique la conexión con el servicio backend.")

    st.markdown("**⚡ Sugerencias rápidas:**")
    sugerencias = [
        "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe",
        "se malogro la faja trasportadora de la linea 3 en packing urjente",
        "cuantos pallets de esparrago verde tenemos listos en almacen",
        "programar camion reefer para despacho de 20 pallets lote L-409 hacia pisco",
    ]

    cols_sug = st.columns(2)
    sug_seleccionada = None
    for idx, s in enumerate(sugerencias):
        col_t = cols_sug[idx % 2]
        label = s if len(s) < 36 else s[:34] + "..."
        if col_t.button(f"📌 {label}", key=f"sug_{idx}", use_container_width=True):
            sug_seleccionada = s

    # Mostrar historial del chat
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            if isinstance(msg["content"], dict):
                st.markdown(formatear_respuesta_humana(msg["content"]))
            else:
                st.markdown(msg["content"])

    user_input = st.chat_input("Escribe tu reporte operativo aquí...")
    prompt_final = sug_seleccionada or user_input

    if prompt_final:
        st.session_state.chat_history.append({"role": "user", "content": prompt_final})
        with st.chat_message("user"):
            st.markdown(prompt_final)

        with st.chat_message("assistant"):
            if not server_online:
                st.error("No se pudo enviar. El servidor está fuera de línea.")
            else:
                with st.spinner("Procesando comando operativo..."):
                    status_c, res_data = api_request("POST", "/nlp/entender-comando", {"texto": prompt_final})
                    if status_c == 200:
                        # Respuesta amigable
                        resp_humana = formatear_respuesta_humana(res_data)
                        st.markdown(resp_humana)

                        # Tarjeta técnica desplegable
                        with st.expander("🔍 Detalle del Análisis NLP y Decisión"):
                            st.write(f"**Intención:** `{res_data.get('intencion')}` ({float(res_data.get('confianza_intencion', 0))*100:.1f}%)")
                            st.write(f"**Sentimiento:** `{res_data.get('sentimiento')}` ({float(res_data.get('confianza_sentimiento', 0))*100:.1f}%)")
                            st.write(f"**Acción Sugerida:** `{res_data.get('accion_sugerida')}`")
                            st.json(res_data.get("entidades", {}))

                        st.session_state.chat_history.append({"role": "assistant", "content": resp_humana})
                    else:
                        st.error(f"Error {status_c}: {res_data}")

    # Sección de Prueba de Auditoría RBAC
    st.write("")
    st.divider()
    with st.expander("🛡️ Prueba de Auditoría RBAC (Demostración de Seguridad en Vivo)", expanded=False):
        st.markdown(
            """
            Esta prueba demuestra en vivo el principio de **Privilegio Mínimo (*Least Privilege*)**:
            Como usuario con rol **OPERADOR**, tus peticiones a la API portan un token JWT válido pero sin permisos para acceder al endpoint administrativo `/nlp/estadisticas`.
            """
        )
        if st.button("🚨 Intentar consultar /nlp/estadisticas (Sin permisos de Supervisor)", type="secondary"):
            status_c, res_data = api_request("GET", "/nlp/estadisticas")
            if status_c == 403:
                st.error(
                    f"""
                    **🚫 HTTP 403 Forbidden — Acceso Bloqueado Exitosamente por el Servidor**
                    
                    **Respuesta del Backend:**  
                    ```json
                    {json.dumps(res_data, indent=2, ensure_ascii=False) if isinstance(res_data, dict) else res_data}
                    ```
                    *Demostración exitosa: El servidor validó el token JWT pero rechazó la petición por falta de rol SUPERVISOR.*
                    """
                )
            else:
                st.warning(f"Respuesta inesperada ({status_c}): {res_data}")


# ====================================================================
# PANTALLA 3: VISTA ROL == SUPERVISOR
# ====================================================================
elif st.session_state.role == "SUPERVISOR":
    st.markdown('<div class="main-title">📊 Centro de Monitoreo y Analítica Operativa — Vista Supervisor</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-title">Panel Administrativo &bull; Sesión: <b>{st.session_state.username}</b> &bull; Región Ica (Uva de Mesa y Espárragos)</div>',
        unsafe_allow_html=True,
    )

    # Controles en Barra Lateral para Supervisor
    auto_refresh = st.sidebar.toggle(
        "🔄 Auto-actualizar cada 5s",
        value=True,
        help="Monitorea en tiempo real los reportes que ingresan desde las terminales de campo",
    )

    if st.sidebar.button("🗑️ Reiniciar Estadísticas", use_container_width=True, type="secondary"):
        status_reset, res_reset = api_request("POST", "/nlp/estadisticas/reiniciar")
        if status_reset == 200:
            st.sidebar.success("✅ Estadísticas restablecidas a cero.")
            time.sleep(0.4)
            st.rerun()
        else:
            st.sidebar.error(f"Error al reiniciar ({status_reset}): {res_reset}")

    with st.sidebar.expander("⚡ Simular Lote (8 Mensajes)", expanded=False):
        st.caption("Poblar métricas de prueba sin usar el celular:")
        if st.button("🚀 Ejecutar Lote de Prueba", use_container_width=True):
            bateria = [
                "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe",
                "se malogro la faja trasportadora de la linea 3 en packing urjente",
                "cuantos pallets de esparrago verde tenemos listos en almacen",
                "programar camion reefer para despacho de 20 pallets lote L-409 hacia pisco",
                "el lote L-512 de uva sweet globe paso control de calidad sin observaciones",
                "compresor del tunel 1 presentando ruido fuerte y perdida de frio",
                "necesito saber cuantas jabas cosecheras y bolsas SO2 quedan en bodega",
                "revisar lo que quedo pendiente ayer en la tarde con el encargado",
            ]
            exitos = 0
            for msg in bateria:
                sc, _ = api_request("POST", "/nlp/entender-comando", {"texto": msg})
                if sc == 200:
                    exitos += 1
            st.sidebar.success(f"✅ {exitos} mensajes procesados y registrados.")
            time.sleep(0.4)
            st.rerun()

    # Pestañas para el Supervisor
    tab_dash, tab_sim = st.tabs(["📈 Dashboard Analítico y Bitácora", "🧪 Consola de Prueba / Simulador"])

    with tab_dash:
        # Obtener estadísticas con el token del Supervisor
        stats = {
            "total_mensajes": 0,
            "por_intencion": {},
            "por_sentimiento": {},
            "confianza_promedio": 0.0,
            "tasa_derivacion": 0.0,
            "entidades_frecuentes": {},
            "ultimos_mensajes": [],
        }

        if server_online:
            st_code, data_stats = api_request("GET", "/nlp/estadisticas")
            if st_code == 200:
                stats = data_stats
            else:
                st.warning(f"No se pudieron cargar las estadísticas ({st_code}): {data_stats}")

        total_mensajes = stats.get("total_mensajes", 0)
        por_intencion = stats.get("por_intencion", {})
        por_sentimiento = stats.get("por_sentimiento", {})
        confianza_promedio = stats.get("confianza_promedio", 0.0)
        tasa_derivacion = stats.get("tasa_derivacion", 0.0)
        entidades_frecuentes = stats.get("entidades_frecuentes", {})
        ultimos_mensajes = stats.get("ultimos_mensajes", [])

        # Conteo de Alertas Críticas
        alertas_criticas = 0
        for m in ultimos_mensajes:
            if m.get("accion_sugerida") in ["ALERTA_CRITICA_CALIDAD", "ORDEN_MANTENIMIENTO_URGENTE"]:
                alertas_criticas += 1
        if total_mensajes > len(ultimos_mensajes) and alertas_criticas == 0:
            alertas_criticas = por_intencion.get("FALLA_EQUIPO", 0) + por_intencion.get("REPORTE_CALIDAD", 0)

        # 1. Fila de 4 KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Mensajes Procesados", total_mensajes)
        k2.metric("Confianza Promedio", f"{confianza_promedio * 100:.1f}%")
        k3.metric("Tasa de Derivación", f"{tasa_derivacion * 100:.1f}%", help="Proporción derivada a supervisor por baja confianza")
        k4.metric("Alertas Críticas Registradas", alertas_criticas, help="ALERTA_CRITICA_CALIDAD y ORDEN_MANTENIMIENTO_URGENTE")

        st.markdown("<br>", unsafe_allow_html=True)

        # 2. Distribución Visual (Gráficos)
        cg1, cg2 = st.columns(2)
        with cg1:
            st.markdown("**📊 Distribución por Intención Operativa**")
            if por_intencion and any(v > 0 for v in por_intencion.values()):
                df_intent = pd.DataFrame(
                    list(por_intencion.items()),
                    columns=["Intención", "Conteo"],
                ).set_index("Intención")
                st.bar_chart(df_intent, color="#2563EB", use_container_width=True)
            else:
                st.info("Sin registros de intenciones aún.")

        with cg2:
            st.markdown("**😊 Distribución por Sentimiento**")
            if por_sentimiento and any(v > 0 for v in por_sentimiento.values()):
                df_sent = pd.DataFrame(
                    list(por_sentimiento.items()),
                    columns=["Sentimiento", "Conteo"],
                ).set_index("Sentimiento")
                st.bar_chart(df_sent, color="#10B981", use_container_width=True)
            else:
                st.info("Sin registros de sentimientos aún.")

        # 3. Ranking de Entidades y Bitácora
        st.markdown("<br>", unsafe_allow_html=True)
        cb1, cb2 = st.columns([1, 2])
        with cb1:
            st.markdown("**🏷️ Entidades y Áreas Más Reportadas**")
            if entidades_frecuentes:
                df_ent = pd.DataFrame(
                    list(entidades_frecuentes.items()),
                    columns=["Entidad / Recurso", "Frecuencia"],
                ).head(10)
                st.dataframe(df_ent, hide_index=True, use_container_width=True)
            else:
                st.info("Aún no se han acumulado entidades.")

        with cb2:
            st.markdown("**📋 Bitácora Reciente de Mensajes (Últimos 15)**")
            if ultimos_mensajes:
                tabla = []
                for reg in ultimos_mensajes:
                    ts = reg.get("timestamp", "")
                    hora = ts[11:19] if len(ts) >= 19 else ts
                    ents = reg.get("entidades", {})
                    ents_resumen = ", ".join([f"{k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in ents.items() if v]) or "—"
                    tabla.append({
                        "Hora (UTC)": hora,
                        "Texto": reg.get("texto_original", ""),
                        "Intención": reg.get("intencion", ""),
                        "Conf. (%)": f"{float(reg.get('confianza_intencion', 0.0)) * 100:.1f}",
                        "Sent.": reg.get("sentimiento", ""),
                        "Entidades": ents_resumen,
                        "Acción": reg.get("accion_sugerida", ""),
                    })
                st.dataframe(pd.DataFrame(tabla), hide_index=True, use_container_width=True)
            else:
                st.info("Bitácora vacía. Los reportes operativos procesados aparecerán aquí en vivo.")

    with tab_sim:
        st.markdown("#### 🧪 Consola de Prueba Directa")
        st.caption("Prueba cómo el motor de inferencia clasifica cualquier texto y emite acciones:")
        sim_texto = st.text_input("Ingresa un mensaje agroexportador:", value="La camara 3 subio a 8 grados con uva sweet globe", key="sim_input")
        if st.button("Analizar Comando", type="primary"):
            st_sim, data_sim = api_request("POST", "/nlp/entender-comando", {"texto": sim_texto})
            if st_sim == 200:
                c1, c2, c3 = st.columns(3)
                c1.metric("Intención", data_sim.get("intencion"))
                c2.metric("Confianza", f"{float(data_sim.get('confianza_intencion', 0))*100:.1f}%")
                c3.metric("Sentimiento", data_sim.get("sentimiento"))
                st.markdown(f'<div class="badge-action">Acción Sugerida: {data_sim.get("accion_sugerida")}</div>', unsafe_allow_html=True)
                st.json(data_sim)
            else:
                st.error(f"Error {st_sim}: {data_sim}")

    # Auto-refresco
    if auto_refresh:
        time.sleep(5)
        st.rerun()
