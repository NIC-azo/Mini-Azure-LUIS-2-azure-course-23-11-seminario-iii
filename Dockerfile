FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    MONOLITH_MODE=true

# Instalar Nginx ligero, gettext (para envsubst) y curl para healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx-light \
    gettext-base \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias unificadas de backend y frontend
COPY requirements-monolith.txt /app/requirements.txt
RUN pip install --no-cache-dir --default-timeout=1000 -r /app/requirements.txt

# Copiar directorios de código y datos
COPY server/ /app/server/
COPY client/ /app/client/

# Copiar plantilla Nginx y script de arranque
COPY nginx.conf.template /app/nginx.conf.template
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Puerto estándar expuesto (Render mapeará dinámicamente $PORT)
EXPOSE 10000

CMD ["/app/start.sh"]
