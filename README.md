# Mini-Azure LUIS v2 🌾

Motor Cloud/On-Premise de Comprensión de Lenguaje Natural (NLP) y Analítica Operativa para la Industria Agroexportadora con Seguridad JWT y Control de Acceso Basado en Roles (RBAC).

Evolución de Mini-Azure LUIS hacia la nube, desarrollado para emular la funcionalidad de **Azure AI Language / LUIS** con soporte para arquitecturas públicas seguras en la nube y despliegue híbrido/local, especializado en la gestión de **uva de mesa** (Red Globe, Sweet Globe, Autumn Crisp, uva sin pepa) y **espárragos** (verde y blanco) en la región de Ica, Perú.

---

## 🏛️ Arquitectura del Sistema

El proyecto está diseñado bajo una arquitectura de microservicios desacoplados con soporte para despliegue local y en plataformas PaaS de nube gratuita:

```text
mini-azure-luis/
├── .env                        # Variables de entorno locales reales (ignorado en Git)
├── .env.example                # Plantilla documentada de variables de entorno y seguridad
├── .gitignore                  # Exclusiones de Git (entorno, modelos temporales, caches)
├── docker-compose.yml          # Orquestación local de microservicios con develop.watch
├── Dockerfile                  # Empaquetado monolítico unificado para Cloud (Render Free)
├── nginx.conf.template         # Plantilla de proxy inverso ligero con soporte WebSocket
├── start.sh                    # Script de orquestación interna (FastAPI + Streamlit + Nginx)
├── requirements-monolith.txt   # Dependencias consolidadas para producción
├── README.md                   # Documentación de funcionamiento y contenido del proyecto
├── docs/
│   ├── ficha_tecnica.md        # Entregable v1: Topología LAN, evidencias y cuadro comparativo
│   ├── persistencia_efimera.md # Resiliencia de almacenamiento en cold starts de nubes gratuitas
│   └── arquitectura_cloud_seguridad.md # Evaluación cloud (Grok) y diseño RBAC con JWT
├── server/                     # [Servicio Backend] Motor NLP + API REST FastAPI (Puerto 8001)
│   ├── Dockerfile              # Imagen Python 3.11-slim optimizada
│   ├── requirements.txt        # Dependencias: FastAPI, Uvicorn, Scikit-Learn, Pandas, PyJWT
│   ├── data/
│   │   ├── dataset_agro.csv    # Corpus de 180 registros balanceados en español
│   │   └── historial.json      # Almacén persistente con control de concurrencia y autoreparación
│   ├── models/                 # Artefactos entrenados (.joblib)
│   └── app/
│       ├── __init__.py
│       ├── auth.py             # Módulo de autenticación JWT y dependencias RBAC (401/403)
│       ├── config.py           # Resolución de variables de entorno, seguridad JWT y rutas
│       ├── train.py            # Pipeline TF-IDF + LogisticRegression
│       ├── nlp_engine.py       # Motor AgroNLPEngine: inferencia, entidades y fallback
│       ├── analytics.py        # Gestor de analítica concurrente tolerante a cold starts
│       └── main.py             # Endpoints FastAPI protegidos con lifespan y CORS
├── client/                     # [Servicio Frontend] Cliente Web + Dashboard Streamlit (Puerto 8501)
│   ├── Dockerfile              # Imagen Python 3.11-slim con PYTHONPATH configurado
│   ├── requirements.txt        # Dependencias: Streamlit, Requests, Pandas, Dotenv
│   └── app/
│       ├── __init__.py
│       ├── config.py           # Resolución dinámica de URL pública Cloud, Monolito y LAN
│       └── dashboard.py        # Interfaz web con Login Gate y vistas diferenciadas por rol
└── tests/
    ├── test_auth_rbac.py       # Pruebas unitarias y de integración de seguridad (401, 403, 200)
    └── test_monolith.py        # Validación de enrutamiento monolítico en puerto único ($PORT)
```

---

## 🧠 Motor de Inteligencia Artificial (NLP Local)

El backend de inferencia combina procesamiento de lenguaje natural estadístico con extracción híbrida de entidades de dominio:

### 1. Clasificación de Intenciones y Sentimientos
- **Vectorización:** `TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, strip_accents='unicode', stop_words=SPANISH_STOPWORDS)`.
- **Clasificadores:** `LogisticRegression(C=2.0, class_weight='balanced', max_iter=1000)` con probabilidades calibradas mediante `predict_proba()`.
- **Intenciones Obligatorias:**
  - `REPORTE_CALIDAD`: Problemas de temperatura en cámaras, humedad relativa, *Botrytis* / pudrición gris, deshidratación de raquis o calibre fuera de norma.
  - `FALLA_EQUIPO`: Averías en túneles de prefrío, fajas transportadoras, balanzas electrónicas, etiquetadoras térmicas y lectores láser.
  - `CONSULTA_INVENTARIO`: Disponibilidad de pallets armados, jabas cosecheras, cajas de cartón, bolsas generadoras de $SO_2$ o stock en cámara.
  - `SOLICITUD_DESPACHO`: Programación de reefers, guías de remisión, certificados fitosanitarios SENASA y salidas a puerto (Callao/Pisco).
- **Sentimientos:** `POSITIVO`, `NEUTRAL`, `NEGATIVO`.

### 2. Extracción de Entidades Normalizadas
El motor extrae y estandariza 4 familias de entidades agroexportadoras:
- **`AREA`:** `camara de frio N`, `tunel de prefrio N`, `linea N`, `muelle N`, `packing`, `almacen`, `recepcion`, `bodega`.
- **`PRODUCTO`:** Normalización automática de variantes ortográficas (`uva red globe`, `uva sweet globe`, `uva autumn crisp`, `uva sin pepa`, `esparrago verde`, `esparrago blanco`).
- **`CANTIDAD`:** Magnitudes y unidades operativas (`120 cajas`, `20 pallets`, `50 jabas`, `9 grados`, `8 °c`, `15 parihuelas`).
- **`CODIGO_LOTE`:** Códigos de trazabilidad interna (`L-512`, `LT-409`, `LOTE-123`).

### 3. Regla de Fallback y Decisión Operativa
Si la confianza de la intención es inferior al umbral configurado (`CONFIDENCE_THRESHOLD = 0.65`) o el texto contiene menos de dos palabras válidas:
- **Intención:** `INTENCION_NO_CLARA`
- **Acción Sugerida:** `DERIVAR_A_SUPERVISOR`

En caso afirmativo, la intención y el sentimiento se mapean automáticamente a la acción operativa correspondiente (`ALERTA_CRITICA_CALIDAD`, `ORDEN_MANTENIMIENTO_URGENTE`, `CONSULTAR_ERP_ALMACEN` o `PROGRAMAR_LOGISTICA_SALIDA`).

---

## 🌐 Endpoints de la API REST (FastAPI - Puerto 8001)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/health` o `/` | Healthcheck del servicio, versión del motor y umbral de confianza activo. |
| `POST` | `/nlp/analizar-texto` | Clasifica sentimiento, confianza y extrae las 4 palabras clave TF-IDF principales. |
| `POST` | `/nlp/entender-comando` | Clasifica intención, sentimiento, entidades, acción sugerida y persiste en bitácora. |
| `GET` | `/nlp/estadisticas` | Retorna los KPIs acumulados: total, por intención, por sentimiento, confianza promedio, tasa de derivación, ranking de entidades y últimos 15 mensajes. |
| `POST` | `/nlp/estadisticas/reiniciar` | Limpia el archivo de persistencia `historial.json` y restablece los KPIs a cero. |

---

## 🖥️ Cliente y Dashboard Streamlit (Puerto 8501)

La interfaz web implementa una separación estricta de responsabilidades según el dispositivo:

1. **Terminal Operativa Móvil (Celulares Android / iOS en Campo):**
   - **Detección Automática:** Inspecciona la cabecera `User-Agent`.
   - **Ocultamiento Total de Sidebar:** Suprime la barra lateral y su botón de despliegue (`>>`).
   - **Cero KPIs ni Métricas:** No muestra ningún indicador analítico, gráfico ni bitácora global.
   - **Respuesta Pura del Modelo:** El operario ingresa su reporte y recibe directamente el objeto JSON de inferencia devuelto por `POST /nlp/entender-comando` (`texto_original`, `intencion`, `confianza_intencion`, `sentimiento`, `entidades` y `accion_sugerida`).

2. **Estación Central de Monitoreo (Dashboard Ligero en PC):**
   - **Control de Red LAN:** Configuración de IP/puerto y verificación con `/health`.
   - **Panel Analítico en Vivo (`GET /nlp/estadisticas`):**
     - 4 KPIs: Total Mensajes Procesados, Confianza Promedio, Tasa de Derivación y Alertas Críticas (diseño Dark Mode de alto contraste).
     - 2 Gráficos de barras interactivos (Distribución por Intención y Sentimiento).
     - Ranking de Entidades y Áreas más reportadas.
     - Bitácora dinámica de los últimos 15 eventos registrados.
     - **Auto-actualización cada 3s:** Para observar en la pantalla central cómo se actualizan las métricas en tiempo real a medida que los operarios envían reportes desde el campo.

---

## 🚀 Guía de Despliegue y Ejecución

### Requisitos Previos
- Docker Desktop en Windows 11 (o Linux/macOS) con soporte para Docker Compose v2.
- Git.

### Opción 1: Desarrollo en una Sola PC (Localhost)
Para levantar ambos contenedores con sincronización en caliente:
```bash
docker compose up -d
```
O con recarga automática activa:
```bash
docker compose up --watch
```
- **API FastAPI:** `http://localhost:8001` (Documentación Swagger en `http://localhost:8001/docs`)
- **Dashboard Streamlit:** `http://localhost:8501`

---

### Opción 2: Demostración en Red Local LAN (Evaluación en Laboratorio)

#### 1. Configuración en la PC Servidor (Integrante A)
1. Abrir PowerShell como **Administrador** y habilitar el puerto 8001 en el Firewall de Windows:
   ```powershell
   New-NetFirewallRule -DisplayName "Mini-Azure-LUIS-API-8001" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
   ```
2. Obtener la IPv4 privada ejecutando `ipconfig` (ejemplo: `192.168.1.45`).
3. Iniciar únicamente el backend:
   ```bash
   docker compose up nlp-server -d
   ```

#### 2. Configuración en la PC Cliente (Integrante B)
1. En el archivo `.env` de la PC Cliente (o directamente desde la barra lateral de Streamlit):
   ```env
   TARGET_SERVER_IP=192.168.1.45
   SERVER_PORT=8001
   ```
2. Iniciar el cliente:
   ```bash
   docker compose up nlp-client -d
   ```
3. Abrir en el navegador `http://localhost:8501` y validar que el semáforo muestre `🟢 Servidor Conectado`.

---

### Opción 3: Despliegue en la Nube Gratuita (Render Free - Modo Monolito)

Arquitectura optimizada para **Render Free Web Service** (< 512 MB RAM) con un solo puerto público dinámico `$PORT` mediante proxy inverso Nginx:

1. **Construcción y Prueba Local:**
   ```bash
   docker build -t mini-azure-luis-monolith .
   docker run -d -p 10000:10000 -e PORT=10000 --env-file .env mini-azure-luis-monolith
   python tests/test_monolith.py
   ```
2. **Despliegue Continuo en Render:**
   - Crear un **Web Service** conectado al repositorio GitHub.
   - **Environment / Runtime:** `Docker`.
   - **Instance Type:** `Free`.
   - **Variables de Entorno en el Dashboard de Render:**
     - `JWT_SECRET_KEY`: Tu clave secreta criptográfica.
     - `OPERADOR_USER`: `operador_ica`
     - `OPERADOR_PASS`: `operador_pass_2026`
     - `SUPERVISOR_USER`: `supervisor_ica`
     - `SUPERVISOR_PASS`: `supervisor_pass_2026`
     - `CONFIDENCE_THRESHOLD`: `0.65`
   - Render construirá automáticamente la imagen desde el `Dockerfile` de la raíz y asignará una URL pública HTTPS (`https://tu-servicio.onrender.com`).
   - Acceso web: La raíz `/` expone directamente el **Login Gate** de Streamlit.
   - Acceso API REST: Los endpoints `/health`, `/auth/login` y `/nlp/*` están disponibles directamente bajo la misma URL pública.

---

## 🔄 Reentrenamiento del Modelo

Si editas o amplías el corpus en `server/data/dataset_agro.csv`, puedes reentrenar los modelos `.joblib` al instante sin reconstruir la imagen:

- **Desde el host:**
  ```bash
  python server/app/train.py
  ```
- **Dentro del contenedor Docker:**
  ```bash
  docker compose exec nlp-server python app/train.py
  ```
