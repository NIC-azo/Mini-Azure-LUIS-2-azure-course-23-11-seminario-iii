import os
from dotenv import load_dotenv

load_dotenv()

TARGET_SERVER_IP = os.getenv("TARGET_SERVER_IP", "127.0.0.1")
SERVER_PORT = os.getenv("SERVER_PORT", "8001")
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "").strip()


def get_api_base_url(custom_ip: str = None, custom_port: str = None) -> str:
    """
    Construye la URL base del servidor NLP.
    Prioridad:
    1. Si se especifica custom_ip en la UI del Dashboard, se utiliza dicha IP/host.
    2. Si existe API_PUBLIC_URL configurada en el entorno (ej. despliegue en la nube HTTPS),
       se utiliza directamente.
    3. Si corre dentro de un contenedor Docker local y se indica 127.0.0.1/localhost,
       resuelve automáticamente a 'nlp-server'.
    4. Fallback estándar a http://TARGET_SERVER_IP:SERVER_PORT.
    """
    if custom_ip and custom_ip.strip():
        port = custom_port.strip() if custom_port and custom_port.strip() else SERVER_PORT
        return f"http://{custom_ip.strip()}:{port}"

    if API_PUBLIC_URL:
        # Remover barra final si existe
        return API_PUBLIC_URL.rstrip("/")

    ip = TARGET_SERVER_IP
    port = SERVER_PORT

    # Si estamos dentro del contenedor Docker y se pasa localhost/127.0.0.1
    if os.path.exists("/.dockerenv") and ip in ["127.0.0.1", "localhost"]:
        ip = "nlp-server"

    return f"http://{ip}:{port}"
