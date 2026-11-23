#!/bin/bash
set -e

# Asignar puerto dinámico de Render o fallback a 10000
export PORT=${PORT:-10000}
echo "=================================================================="
echo "🌾 INICIANDO MINI-AZURE LUIS v2 EN MODO MONOLITO"
echo "🌐 Puerto Público Expuesto (\$PORT): ${PORT}"
echo "=================================================================="

# 1. Configurar Nginx con el puerto dinámico de Render usando envsubst
echo "⚙️ Configurando proxy inverso Nginx para puerto ${PORT}..."
rm -f /etc/nginx/sites-enabled/default
envsubst '$PORT' < /app/nginx.conf.template > /etc/nginx/conf.d/default.conf

# 2. Iniciar FastAPI en segundo plano en 127.0.0.1:8001
echo "🚀 Iniciando Backend FastAPI en 127.0.0.1:8001..."
cd /app/server
uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1 &
FASTAPI_PID=$!

# 3. Iniciar Streamlit en segundo plano en 127.0.0.1:8501
echo "📊 Iniciando Frontend Streamlit en 127.0.0.1:8501..."
cd /app/client
streamlit run app/dashboard.py \
    --server.port=8501 \
    --server.address=127.0.0.1 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false &
STREAMLIT_PID=$!

# 4. Esperar brevemente a que los servicios internos estén en línea
echo "⏳ Esperando inicialización de servicios internos..."
sleep 4

# 5. Iniciar Nginx en primer plano (mantiene vivo el contenedor)
echo "🟢 Servicios internos activos. Arrancando Nginx en primer plano..."
exec nginx -g 'daemon off;'
