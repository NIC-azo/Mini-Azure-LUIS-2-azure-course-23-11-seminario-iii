import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Asegurar importación de módulos locales
current_dir = Path(__file__).resolve().parent
server_dir = current_dir.parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from app.config import (
    SERVER_HOST,
    SERVER_PORT,
    CONFIDENCE_THRESHOLD,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.nlp_engine import AgroNLPEngine
from app.analytics import (
    registrar_evento,
    obtener_estadisticas,
    reiniciar_estadisticas,
)
from app.auth import (
    authenticate_user,
    create_access_token,
    require_role,
)

# Variable global para el motor NLP cargado en memoria
nlp_engine: Optional[AgroNLPEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de FastAPI: Carga los modelos entrenados al iniciar."""
    global nlp_engine
    print("🌾 Cargando modelos de inferencia NLP en memoria...")
    try:
        nlp_engine = AgroNLPEngine()
        print("✅ Motor AgroNLPEngine cargado y listo para recibir peticiones.")
    except Exception as e:
        print(f"⚠️ Advertencia al inicializar AgroNLPEngine: {e}")
        print("Asegúrese de haber ejecutado 'python app/train.py' previamente.")
    yield
    print("Cerrando servicio NLP...")


app = FastAPI(
    title="Mini-Azure LUIS v2 API",
    description="Motor de Inferencia NLP Cloud/On-Premise con Seguridad JWT y Control de Acceso Basado en Roles (RBAC)",
    version="2.0.0",
    lifespan=lifespan,
)

# Habilitar CORS para permitir consumo desde el Dashboard Streamlit o cualquier cliente Cloud / LAN
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------
# Esquemas Pydantic
# -------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(..., description="Nombre de usuario registrado", examples=["operador_ica", "supervisor_ica"])
    password: str = Field(..., description="Contraseña de acceso")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    expires_in_minutes: int


class TextoRequest(BaseModel):
    texto: str = Field(
        ...,
        description="Mensaje u orden operativa en lenguaje natural",
        examples=["La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe"],
        min_length=1,
    )


class AnalisisTextoResponse(BaseModel):
    texto_original: str
    sentimiento: str
    confianza_sentimiento: float
    palabras_clave: List[str]


class EntenderComandoResponse(BaseModel):
    texto_original: str
    intencion: str
    confianza_intencion: float
    sentimiento: str
    confianza_sentimiento: float
    entidades: Dict[str, List[str]]
    palabras_clave: List[str]
    accion_sugerida: str


# -------------------------------------------------------------
# Endpoints de la API
# -------------------------------------------------------------
@app.get("/", tags=["Salud"])
@app.get("/health", tags=["Salud"])
def health_check():
    """Verifica la disponibilidad del servicio y los parámetros activos."""
    return {
        "status": "online",
        "servicio": "Mini-Azure LUIS v2 NLP Engine",
        "version": "2.0.0",
        "puerto": SERVER_PORT,
        "host": SERVER_HOST,
        "umbral_confianza": CONFIDENCE_THRESHOLD,
        "motor_cargado": nlp_engine is not None,
    }


@app.post(
    "/auth/login",
    response_model=LoginResponse,
    tags=["Autenticación"],
    summary="Inicio de Sesión y Emisión de Token JWT",
)
def login_endpoint(credentials: LoginRequest):
    """
    Autentica al usuario contra las credenciales del sistema y emite un token JWT
    con rol asignado ('OPERADOR' o 'SUPERVISOR').
    Lanza 401 Unauthorized si las credenciales son inválidas.
    """
    user = authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas: usuario o contraseña no válidos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user["role"],
        "username": user["username"],
        "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
    }


@app.post(
    "/nlp/analizar-texto",
    response_model=AnalisisTextoResponse,
    tags=["NLP"],
    summary="Análisis de Sentimiento y Text Analytics",
)
def analizar_texto_endpoint(
    req: TextoRequest,
    current_user: Dict[str, Any] = Depends(require_role(["OPERADOR", "SUPERVISOR"])),
):
    """
    Analiza un texto en español identificando su sentimiento predominante,
    nivel de confianza y las palabras clave con mayor relevancia TF-IDF.
    Requiere rol OPERADOR o SUPERVISOR.
    """
    if nlp_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Motor NLP no disponible. Entrene los modelos con 'train.py'.",
        )

    res = nlp_engine.analizar_texto(req.texto)
    return {
        "texto_original": req.texto,
        "sentimiento": res["sentimiento"],
        "confianza_sentimiento": res["confianza_sentimiento"],
        "palabras_clave": res["palabras_clave"],
    }


@app.post(
    "/nlp/entender-comando",
    response_model=EntenderComandoResponse,
    tags=["NLP"],
    summary="Comprensión de Comandos e Inferencia Operativa",
)
def entender_comando_endpoint(
    req: TextoRequest,
    current_user: Dict[str, Any] = Depends(require_role(["OPERADOR", "SUPERVISOR"])),
):
    """
    Identifica la intención operativa del mensaje, sentimiento, extrae entidades
    del dominio agroexportador y sugiere una acción operativa.
    Registra el evento automáticamente en la persistencia analítica.
    Requiere rol OPERADOR o SUPERVISOR.
    """
    if nlp_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Motor NLP no disponible. Entrene los modelos con 'train.py'.",
        )

    res = nlp_engine.entender_comando(req.texto, umbral_confianza=CONFIDENCE_THRESHOLD)

    # Filtrar categorías vacías de entidades para mantener un JSON limpio y legible
    entidades_limpias = {k: v for k, v in res.get("entidades", {}).items() if v}

    evento = {
        "texto_original": req.texto,
        "intencion": res["intencion"],
        "confianza_intencion": res["confianza_intencion"],
        "sentimiento": res["sentimiento"],
        "confianza_sentimiento": res["confianza_sentimiento"],
        "entidades": entidades_limpias,
        "palabras_clave": res.get("palabras_clave", []),
        "accion_sugerida": res["accion_sugerida"],
    }

    # Registrar el evento en el almacén persistente con control de concurrencia
    registrar_evento(evento)

    return evento


@app.get(
    "/nlp/estadisticas",
    tags=["Analítica"],
    summary="Resumen de Métricas y KPIs de la Operación",
)
def obtener_estadisticas_endpoint(
    current_user: Dict[str, Any] = Depends(require_role(["SUPERVISOR"])),
):
    """
    Devuelve los KPIs acumulados: total de mensajes, distribución por intención,
    sentimiento, confianza promedio, tasa de derivación, entidades frecuentes y bitácora.
    Requiere rol exclusivo SUPERVISOR (OPERADOR recibe 403 Forbidden).
    """
    return obtener_estadisticas()


@app.post(
    "/nlp/estadisticas/reiniciar",
    tags=["Analítica"],
    summary="Reinicia el Historial y Métricas Acumuladas",
)
def reiniciar_estadisticas_endpoint(
    current_user: Dict[str, Any] = Depends(require_role(["SUPERVISOR"])),
):
    """
    Restablece a cero todos los contadores y limpia el archivo historial.json.
    Requiere rol exclusivo SUPERVISOR (OPERADOR recibe 403 Forbidden).
    """
    return reiniciar_estadisticas()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=SERVER_HOST, port=SERVER_PORT, reload=True)
