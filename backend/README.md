# Azure Web PubSub + Microsoft Agent Framework

Demo **plug-and-play** en Python para procesamiento de mensajes en tiempo real usando:

- **Azure Web PubSub** (frontend + backend sobre **WebSocket**)
- **Microsoft Agent Framework (Python)** para la respuesta del agente
- **Flujo de agentes** (pipeline: `Intent -> Enrichment -> Response`)
- **Flujo SQLAgentX** (pipeline: `Planner -> Librarian -> SQL Coder -> SQL Execution -> Evaluator`)
- **FastAPI** para health, negociación y operación local
- **Docker opcional**

> Este módulo está aislado y no mezcla nada con el código Next.js.

---

## 1) Estructura

```text
python-rt-agent-demo/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── README.md
├── src/
│   └── app/
│       ├── agents/
│       ├── agent_flow.py
│       ├── backend_listener.py
│       ├── config.py
│       ├── logging_config.py
│       ├── main.py
│       ├── models.py
│       ├── ms_agent_client.py
│       ├── pubsub_protocol.py
│       ├── pubsub_service.py
│       └── static/index.html
└── tests/
```

---

## 2) Pre-requisitos

- Python 3.11+
- UV instalado (https://docs.astral.sh/uv/)
- Un recurso de **Azure Web PubSub**
- Variables de entorno de **Microsoft Agent Framework**

---

## 3) Configuración rápida (Local)

### 3.1 Variables

1. Copia el template:

```bash
cp .env.example .env
```

2. Completa al menos:

- `AZURE_WEBPUBSUB_CONNECTION_STRING`
- `AZURE_WEBPUBSUB_HUB_NAME`
- `AZURE_WEBPUBSUB_GROUP`

3. Completa Agent Framework:

- `AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME`

4. Elige un método de autenticación (sin Azure CLI):

- **Modo A (recomendado para Docker): API key**
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_API_VERSION` (opcional, recomendado)

- **Modo B: identidad administrada / service principal por variables de entorno**
  - `AZURE_AI_PROJECT_ENDPOINT`
  - `AZURE_TENANT_ID`
  - `AZURE_CLIENT_ID`
  - `AZURE_CLIENT_SECRET`

> Este backend corre en modo estricto con Agent Framework. Si faltan estas variables, el procesamiento de respuesta fallará.

5. Si quieres habilitar Query-to-Insight sobre Azure SQL, agrega:

- `AZURE_SQL_CONNECTION_STRING`
- `SQL_QUERY_TIMEOUT_SECONDS` (default: `20`)
- `SQL_ROW_LIMIT` (default: `200`)
- `SQL_MAX_RETRY_CORRECTIONS` (default: `2`)

### 3.2 Instalar y correr con UV (aislado)

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run uvicorn app.main:app --host 0.0.0.0 --port 8010 --app-dir src
```

Con este flujo, todo queda encapsulado en `.venv` dentro de `python-rt-agent-demo`.

Abrir en navegador:

- `http://localhost:8010`

---

## 4) Configuración con Docker (Opcional)

```bash
docker compose up --build
```

Abrir:

- `http://localhost:8010`

---

## 5) Cómo funciona en tiempo real

1. Frontend solicita token en `POST /api/negotiate`
2. Frontend conecta WebSocket al URL firmado de Web PubSub
3. Frontend envía `user.message` al grupo
4. Backend listener (también por WebSocket) consume mensaje del grupo
5. `Planner` enruta:
   - Preguntas analíticas -> `Librarian -> SQL Coder -> SQL Execution -> Evaluator`
   - Preguntas generales -> respuesta de chat en `Evaluator`
6. `SQL Execution` aplica guardrails (`SELECT` only, bloqueo DDL/DML, `TOP` forzado)
7. Backend publica:
   - `status`
   - `assistant.delta` (stream por tokens)
   - `assistant.complete`

---

## 6) API rápida

- `GET /health`
- `GET /ready`
- `POST /api/negotiate`
- `POST /api/messages` (alternativa backend->group)

---

## 7) Calidad y validación

### Tests

```bash
uv run pytest
```

### Lint

```bash
uv run ruff check src tests
```

### Benchmarks Fase 2 (A/B/C)

Ejecuta benchmark sintético reproducible y genera reporte:

```bash
PYTHONPATH=src uv run python scripts/run_benchmarks.py --output reports/benchmark_results.json
PYTHONPATH=src uv run python scripts/generate_benchmark_report.py --input reports/benchmark_results.json --output reports/benchmark_report.md
```

Benchmark live contra Azure SQL (Fase 3):

```bash
PYTHONPATH=src uv run python scripts/run_benchmarks.py --mode live --output reports/benchmark_results_live.json
PYTHONPATH=src uv run python scripts/generate_benchmark_report.py --input reports/benchmark_results_live.json --output reports/benchmark_report_live.md
```

> Requiere `AZURE_SQL_CONNECTION_STRING` configurada. El benchmark live usa consultas seguras sobre `INFORMATION_SCHEMA`.

Suite de tests de benchmark:

```bash
uv run pytest tests/benchmarks -q
```

---

## 8) Seguridad aplicada

- Validación de entrada con Pydantic (`message`, ids, enums)
- Secretos fuera de código (variables de entorno)
- No log de claves
- Tokens de acceso con roles mínimos (`joinLeaveGroup`, `sendToGroup`)
- Manejo de errores y reconexión con backoff + jitter en listener

---

## 9) Mejoras recomendadas (para producción)

1. **Autenticación fuerte de usuario**
   - Agregar JWT o API Gateway delante de `/api/negotiate`.
   - Razón: evitar que cualquier cliente solicite tokens del hub.

2. **Rate limiting y cuotas**
   - Limitar `user.message` por usuario/IP.
   - Razón: mitigación de abuso y costos.

3. **Persistencia y auditoría**
   - Guardar envelopes y estado de conversación en DB (PostgreSQL/Cosmos).
   - Razón: trazabilidad y recuperación.

4. **Observabilidad completa**
   - Métricas (latencia por etapa), tracing distribuido y alertas.
   - Razón: soporte operativo y SLOs.

5. **Idempotencia por `correlation_id`**
   - Deduplicar eventos repetidos por reconexión/reintentos.
   - Razón: consistencia en flujos realtime.

6. **Aislamiento de agentes por interfaz**
   - Mantener contratos de pasos y añadir tests de contrato por agente.
   - Razón: mejor extensibilidad y cumplimiento de SOLID.

7. **Hardening de payloads**
   - Limitar tamaño de `payload`, validación anti-inyección y sanitización.
   - Razón: seguridad y estabilidad.

---

## 10) Troubleshooting

- **No tengo UV instalado**
  - Instálalo desde la documentación oficial de Astral y vuelve a ejecutar `uv venv`.
- **No quiero activar el entorno manualmente**
  - Puedes ejecutar todo con `uv run ...` (sin `source .venv/bin/activate`).

- **No conecta WebSocket**
  - Verifica `AZURE_WEBPUBSUB_CONNECTION_STRING`, hub y grupo.
- **No responde el agente**
  - Revisa logs del listener.
- **No hay salida LLM**
  - Verifica `AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME` y un método de auth:
    - `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY`, o
    - `AZURE_AI_PROJECT_ENDPOINT` + variables de identidad (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`).
