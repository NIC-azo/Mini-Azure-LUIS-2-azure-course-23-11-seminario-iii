import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TARGET_SERVER_IP = os.getenv("TARGET_SERVER_IP", "127.0.0.1")
SERVER_PORT = os.getenv("SERVER_PORT", "8001")
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "").strip()
MONOLITH_MODE = os.getenv("MONOLITH_MODE", "false").lower() in ("true", "1", "yes")


def get_api_base_url(custom_url_or_ip: str = None, custom_port: str = None) -> str:
    """
    Construye la URL base del servidor NLP.
    Prioridad:
    1. Si se especifica una URL o IP personalizada en la barra lateral del Dashboard, se utiliza.
    2. Si corre en modo monolito unificado (Render o contenedor monolítico local),
       conecta internamente a 127.0.0.1:8001 (máxima velocidad, cero latencia externa).
    3. Si existe API_PUBLIC_URL configurada en las variables de entorno (ej. en despliegue Render HTTPS),
       se utiliza directamente.
    4. Si corre dentro de un contenedor Docker tradicional y se indica 127.0.0.1 o localhost,
       resuelve automáticamente a 'nlp-server'.
    5. Fallback estándar a http://TARGET_SERVER_IP:SERVER_PORT.
    """
    if custom_url_or_ip and custom_url_or_ip.strip():
        val = custom_url_or_ip.strip()
        if val.startswith("http://") or val.startswith("https://"):
            return val.rstrip("/")
        port = custom_port.strip() if custom_port and custom_port.strip() else SERVER_PORT
        return f"http://{val}:{port}"

    # Modo Monolito (Render Free / Dockerfile unificado)
    if MONOLITH_MODE:
        return "http://127.0.0.1:8001"

    if API_PUBLIC_URL:
        return API_PUBLIC_URL.rstrip("/")

    ip = TARGET_SERVER_IP
    port = SERVER_PORT

    # Si estamos dentro del contenedor Docker y se pasa localhost o 127.0.0.1
    if os.path.exists("/.dockerenv") and ip in ["127.0.0.1", "localhost"]:
        ip = "nlp-server"

    return f"http://{ip}:{port}"
