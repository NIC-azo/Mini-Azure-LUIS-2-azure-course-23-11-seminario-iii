import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz o entorno actual
load_dotenv()

# BASE_DIR apunta a la carpeta 'server'
BASE_DIR = Path(__file__).resolve().parent.parent

SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8001")))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))

# Configuración de Seguridad y JWT (Fase 0.2 / Fase 2)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "clave_secreta_jwt_mini_azure_luis_v2_segura_2026_agro")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

# Credenciales RBAC
OPERADOR_USER = os.getenv("OPERADOR_USER", "operador_ica")
OPERADOR_PASS = os.getenv("OPERADOR_PASS", "operador_pass_2026")
SUPERVISOR_USER = os.getenv("SUPERVISOR_USER", "supervisor_ica")
SUPERVISOR_PASS = os.getenv("SUPERVISOR_PASS", "supervisor_pass_2026")

# URL Pública de la API
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "")
TARGET_SERVER_IP = os.getenv("TARGET_SERVER_IP", "127.0.0.1")

def get_api_base_url(custom_url_or_ip: str = None, custom_port: str = None) -> str:
    """Fallback para resolución de URL si se importa desde el paquete backend."""
    if custom_url_or_ip and custom_url_or_ip.strip():
        val = custom_url_or_ip.strip()
        if val.startswith("http://") or val.startswith("https://"):
            return val.rstrip("/")
        port = custom_port.strip() if custom_port and custom_port.strip() else SERVER_PORT
        return f"http://{val}:{port}"
    if API_PUBLIC_URL:
        return API_PUBLIC_URL.rstrip("/")
    return f"http://{TARGET_SERVER_IP}:{SERVER_PORT}"

def resolve_path(env_var_name: str, fallback_subpath: str) -> str:
    val = os.getenv(env_var_name)
    if val and os.path.exists(val):
        return val
    # Si viene configurado como /app/... (entorno Docker) pero corre fuera del contenedor
    if val and val.startswith("/app/"):
        rel = val[len("/app/"):]
        candidate = BASE_DIR / rel
        if candidate.exists() or candidate.parent.exists():
            return str(candidate)
    fallback = BASE_DIR / fallback_subpath
    return str(fallback)

DATASET_PATH = resolve_path("DATASET_PATH", "data/dataset_agro.csv")
MODEL_DIR = resolve_path("MODEL_DIR", "models")
STATS_FILE = resolve_path("STATS_FILE", "data/historial.json")
