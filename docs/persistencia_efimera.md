# Persistencia en Entornos Efímeros y Tolerancia a Fallos (Mini-Azure LUIS v2)

## 1. Problemática de los Contenedores Cloud Gratuitos (PaaS)

En plataformas de nube gratuitas como **Render**, **Hugging Face Spaces**, **Koyeb** o **Railway**, las instancias de ejecución funcionan bajo el modelo de **almacenamiento efímero (*ephemeral storage*)**:

1. **Suspensión por Inactividad (*Spin-down* / *Cold Start*):** Cuando no hay tráfico entrante durante un periodo de tiempo (usualmente 15 minutos), el contenedor entra en hibernación o se destruye.
2. **Reinicio de Sistema de Archivos:** Al despertar por una nueva petición HTTP entrante (*cold start*), el contenedor se aprovisiona desde la imagen base original, eliminando cualquier archivo o cambio realizado en disco local que no forme parte de la imagen inicial o de un volumen persistente montado.
3. **Apagados Repentinos:** Si el proveedor suspende el contenedor mientras se ejecuta una escritura en disco, los archivos pueden quedar truncados o corruptos (JSON a medio escribir).

---

## 2. Mecanismo de Resiliencia y Autoreparación (`analytics.py`)

Para garantizar que `Mini-Azure LUIS v2` nunca devuelva un error `500 Internal Server Error` debido a la ausencia o corrupción de `historial.json`, el módulo `server/app/analytics.py` implementa la siguiente estrategia:

### A. Autoconsistencia y Generación Transparente (`_ensure_file`)
- Antes de cualquier operación de lectura o escritura, se invoca `_ensure_file()`.
- Verifica la existencia del directorio padre (`/app/data/`) y lo genera recursivamente (`mkdir(parents=True, exist_ok=True)`).
- Si el archivo `historial.json` no existe (comportamiento típico tras un *cold start*), crea un archivo limpio con la estructura base:
  ```json
  {
    "registros": []
  }
  ```

### B. Tolerancia a Corrupción y Autoreparación (`_read_data`)
- Si un apagado abrupto corrompe el JSON o lo deja con 0 bytes, el bloque `try/except` captura `JSONDecodeError` y cualquier excepción de entrada/salida.
- En caso de anomalía, regenera automáticamente el archivo con estructura vacía válida y retorna `{"registros": []}`, evitando el colapso del endpoint `/nlp/estadisticas`.

### C. Escritura Atómica en Disco (`_write_data`)
- En lugar de sobrescribir directamente `historial.json`, la nueva información se vuelca primero en un archivo temporal (`historial.json.tmp`).
- Una vez completada la escritura en búfer, se realiza un reemplazo atómico a nivel de sistema operativo (`os.replace`). Si el proceso muere en medio de la escritura, el archivo principal `historial.json` permanece íntegro.

### D. Concurrencia Protegida
- Se mantiene un bloqueo de hilos (`threading.Lock`) para sincronizar peticiones concurrentes provenientes de múltiples operadores enviando comandos en simultáneo.

---

## 3. Comportamiento en los Endpoints de la API

| Endpoint | Estado de `historial.json` | Respuesta del Backend | Código HTTP |
| :--- | :--- | :--- | :--- |
| `GET /nlp/estadisticas` | Archivo eliminado (Cold Start) | Retorna KPIs en cero (`total_mensajes: 0`) y autogenera el archivo | `200 OK` |
| `POST /nlp/entender-comando` | Archivo eliminado (Cold Start) | Autogenera el archivo y almacena el evento como `id: 1` | `200 OK` |
| `GET /nlp/estadisticas` | Archivo corrupto (JSON roto) | Repara el archivo a vacío y retorna métricas en cero sin lanzar excepción | `200 OK` |
| `POST /nlp/estadisticas/reiniciar` | Cualquiera | Limpia los registros atómicamente a `{"registros": []}` | `200 OK` |
