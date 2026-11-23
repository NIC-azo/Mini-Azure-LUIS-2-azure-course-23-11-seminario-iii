# Documento de Arquitectura, Investigación Cloud y Seguridad
**Proyecto:** Mini-Azure LUIS v2  
**Especialización:** Seminario de Especialización Cloud & IA (2026)  
**URL Pública en Producción:** [https://mini-azure-luis-v2-kbos.onrender.com](https://mini-azure-luis-v2-kbos.onrender.com)

---

## 1. Credenciales de Demostración y Acceso

Para la evaluación del sistema en producción se han configurado dos perfiles con permisos mutuamente excluyentes:

| Perfil / Rol | Usuario | Contraseña | Alcance de Permisos |
| :--- | :--- | :--- | :--- |
| **OPERADOR** | `operador_ica` | `operador_pass_2026` | **Acceso operativo de campo.** Envío de reportes de calidad, averías, stock y despacho (`POST /nlp/entender-comando`). Bloqueado con **HTTP 403 Forbidden** para métricas y KPIs. |
| **SUPERVISOR** | `supervisor_ica` | `supervisor_pass_2026` | **Acceso total de gestión y auditoría.** Visualización de dashboard analítico en vivo (`GET /nlp/estadisticas`), bitácora completa, simulador de inferencia y reinicio de métricas (`POST /nlp/estadisticas/reiniciar`). |

---

## 2. Investigación y Selección de Plataforma Cloud Gratuita

Para el despliegue del sistema sin costos de infraestructura, se llevó a cabo un benchmark técnico asistido por IA (Grok) evaluando 4 plataformas vigentes:

### Matriz Comparativa de Plataformas Evaluadas

| Plataforma Cloud | Hardware Free Tier (RAM / CPU) | Política de Inactividad (Sleep) | Latencia Cold Start | Soporte Docker / Puerto Único | Veredicto Técnico |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Render** *(Web Service Free)* | **512 MB RAM / 0.5 vCPU** | **15 minutos** de inactividad | 30 - 50 segundos | **Excelente:** Detección automática de Dockerfile raíz, asignación dinámica de `$PORT`, HTTPS gestionado y despliegue continuo desde GitHub. | **1º Lugar (Seleccionada):** La arquitectura monolítica resuelve en un solo contenedor la API y la UI, maximizando la estabilidad de memoria. |
| **Koyeb** *(Free Eco Instance)* | 512 MB RAM / 0.1 vCPU | 1 hora de inactividad | 2 - 5 segundos | Muy bueno (Docker nativo y puerto configurable). | **2º Lugar (Descartada como principal):** Límite estricto de horas de cómputo mensuales en free tier y menor integración directa con repositorios complejos sin tarjeta de crédito. |
| **Streamlit Community Cloud + Render** | Frontend 1 GB RAM / Backend 512 MB | Frontend duerme a las 12h / Backend duerme a los 15 min | Asíncrona (Streamlit despierto pero API dormida) | Arquitectura desacoplada de 2 URLs separadas. | **3º Lugar (Descartada):** Problemas de desincronización de *cold start* (el frontend intentaba consumir una API dormida arrojando errores de conexión) y complejidad innecesaria de CORS. |
| **Hugging Face Spaces** *(Docker)* | 16 GB RAM / 2 vCPU | N/A | N/A | Exige suscripción PRO pagada ($9/mes). | **Descartada:** Modelo gratuito discontinuado para Dockerfiles personalizados. |

### Límites del Plan Gratuito Elegido (Render Free)
- **Memoria RAM (512 MB):** El contenedor debe mantenerse ligero. La combinación de Scikit-Learn (TF-IDF + Regresión Logística), FastAPI y Streamlit optimizado consume ~185 MB en reposo y ~260 MB bajo carga, manteniéndose muy por debajo del límite de OOM (*Out Of Memory*).
- **Almacenamiento Efímero:** El disco local se restablece en cada *cold start*. Este comportamiento fue mitigado en el backend (`analytics.py`) mediante autocreación y autoreparación de `historial.json`.
- **Puerto Único Expuesto (`$PORT`):** Render expone un solo puerto público dinámico. Se solucionó incorporando un proxy inverso ligero (**Nginx**) que recibe el tráfico público y enruta internamente hacia FastAPI (`8001`) y Streamlit (`8501`).

---

## 3. Evidencias de Control de Acceso (Validación Real en Render HTTPS)

Las siguientes evidencias fueron capturadas ejecutando la suite de validación [tests/test_production_render.py](file:///c:/Users/Alumno/Documents/1412994/seminari_III/23_11_ip4/mini-azure-luis/tests/test_production_render.py) sobre la URL de producción `https://mini-azure-luis-v2-kbos.onrender.com`:

### (a) Rechazo sin Autenticación (`HTTP 401 Unauthorized`)
Al intentar consumir cualquier endpoint operativo o administrativo sin cabecera de autorización o con un token inválido:

**Petición:**
```bash
curl -X POST https://mini-azure-luis-v2-kbos.onrender.com/nlp/entender-comando \
  -H "Content-Type: application/json" \
  -d '{"texto": "La camara de frio 2 subio a 9 grados"}'
```

**Respuesta del Servidor (HTTP 401):**
```json
{
  "detail": "No autenticado o token ausente. Proporcione header 'Authorization: Bearer <token>'"
}
```

---

### (b) Operación Exitosa del Usuario de Comentarios / OPERADOR (`HTTP 200 OK`)
El usuario con rol `OPERADOR` inicia sesión, recibe su JWT y envía un reporte operativo de campo:

**1. Login:**
```bash
curl -X POST https://mini-azure-luis-v2-kbos.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "operador_ica", "password": "operador_pass_2026"}'
```
*Respuesta:* Retorna `access_token` firmado criptográficamente con `role: "OPERADOR"`.

**2. Envío de Comando:**
```bash
curl -X POST https://mini-azure-luis-v2-kbos.onrender.com/nlp/entender-comando \
  -H "Authorization: Bearer <TOKEN_OPERADOR>" \
  -H "Content-Type: application/json" \
  -d '{"texto": "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe"}'
```

**Respuesta del Servidor (HTTP 200 OK):**
```json
{
  "texto_original": "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe",
  "intencion": "REPORTE_CALIDAD",
  "confianza_intencion": 0.6516,
  "sentimiento": "NEGATIVO",
  "confianza_sentimiento": 0.6157,
  "entidades": {
    "AREA": [
      "camara de frio 2"
    ],
    "PRODUCTO": [
      "uva red globe"
    ],
    "CANTIDAD": [
      "9 grados",
      "120 cajas"
    ]
  },
  "palabras_clave": [
    "120",
    "120 cajas",
    "frio subio",
    "grados 120"
  ],
  "accion_sugerida": "ALERTA_CRITICA_CALIDAD"
}
```

---

### (c) Restricción de Estadísticas para el Usuario OPERADOR (`HTTP 403 Forbidden`)
Cuando el usuario `OPERADOR` intenta consultar las estadísticas o KPIs del dashboard administrativo:

**Petición:**
```bash
curl -X GET https://mini-azure-luis-v2-kbos.onrender.com/nlp/estadisticas \
  -H "Authorization: Bearer <TOKEN_OPERADOR>"
```

**Respuesta del Servidor (HTTP 403 Forbidden):**
```json
{
  "detail": "Acceso denegado: permisos insuficientes para el rol OPERADOR. Requiere uno de: SUPERVISOR"
}
```
*Demostración en Interfaz Web:* En la vista de operario existe una sección colapsable **"🛡️ Prueba de Auditoría RBAC"** con un botón que ejecuta esta llamada en vivo y despliega la alerta roja de bloqueo.

---

### (d) Acceso Completo al Dashboard para el Usuario SUPERVISOR (`HTTP 200 OK`)
El usuario con rol `SUPERVISOR` accede a todas las métricas analíticas acumuladas:

**Petición:**
```bash
curl -X GET https://mini-azure-luis-v2-kbos.onrender.com/nlp/estadisticas \
  -H "Authorization: Bearer <TOKEN_SUPERVISOR>"
```

**Respuesta del Servidor (HTTP 200 OK):**
```json
{
  "total_mensajes": 15,
  "por_intencion": {
    "REPORTE_CALIDAD": 4,
    "FALLA_EQUIPO": 1,
    "CONSULTA_INVENTARIO": 1,
    "SOLICITUD_DESPACHO": 2,
    "INTENCION_NO_CLARA": 7
  },
  "por_sentimiento": {
    "POSITIVO": 2,
    "NEUTRAL": 5,
    "NEGATIVO": 8
  },
  "confianza_promedio": 0.6036,
  "tasa_derivacion": 0.4667,
  "entidades_frecuentes": {
    "uva red globe": 2,
    "camara de frio 2": 2,
    "9 grados": 2,
    "120 cajas": 2,
    "uva sweet globe": 2,
    "L-512": 2,
    "20 pallets": 2,
    "L-409": 2,
    "linea 3": 1,
    "packing": 1
  },
  "ultimos_mensajes": [
    {
      "id": 15,
      "timestamp": "2026-11-23T21:04:30.841521+00:00",
      "texto_original": "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe",
      "intencion": "REPORTE_CALIDAD",
      "confianza_intencion": 0.6516,
      "sentimiento": "NEGATIVO",
      "confianza_sentimiento": 0.6157,
      "entidades": {
        "AREA": ["camara de frio 2"],
        "PRODUCTO": ["uva red globe"],
        "CANTIDAD": ["9 grados", "120 cajas"]
      },
      "accion_sugerida": "ALERTA_CRITICA_CALIDAD"
    }
  ]
}
```

---

## 4. Arquitectura de Despliegue en Puerto Único ($PORT)

Render asigna dinámicamente un puerto de escucha en la variable `$PORT`. El flujo de peticiones dentro del contenedor monolítico opera de la siguiente manera:

```text
                  Internet (HTTPS)
                         │
                         ▼
             [ Puerto Público : $PORT ]
                         │
                         ▼
        ┌───────────────────────────────────┐
        │        Nginx Proxy Inverso        │
        └─────────────────┬─────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
   Rutas de API REST             Rutas Web y Sockets
   /(auth|nlp|health|docs)       / y /_stcore/stream
          │                               │
          ▼                               ▼
┌──────────────────┐            ┌──────────────────┐
│ FastAPI Backend  │            │ Streamlit UI     │
│ (127.0.0.1:8001) │◄───────────│ (127.0.0.1:8501) │
└──────────────────┘  Internal   └──────────────────┘
                      API Calls
```

- **Rendimiento Interno:** La comunicación interna entre Streamlit y FastAPI se realiza directamente sobre `http://127.0.0.1:8001` sin pasar por la red pública, reduciendo la latencia de procesamiento a menos de 5 ms.
- **Soporte de WebSockets:** Nginx incluye los encabezados `Upgrade` y `Connection "upgrade"` con un `proxy_read_timeout 86400s`, garantizando la actualización reactiva en tiempo real del dashboard de Streamlit.
