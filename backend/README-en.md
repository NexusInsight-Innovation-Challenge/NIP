[Versión español](./README.md)
# Innovation Challenge Chat | Azure Web PubSub + Microsoft Agent Framework

A **plug-and-play** Python demo for real-time message processing using:

- **Azure Web PubSub** (frontend + backend over **WebSockets**)
- **Microsoft Agent Framework (Python)** for agent responses
- **Agent Flow** (pipeline: `Intent -> Enrichment -> Response`)
- **SQLAgentX Flow** (pipeline: `Planner -> Librarian -> SQL Coder -> SQL Execution -> Evaluator`)
- **FastAPI** for health checks, negotiation, and local operation
- **Optional Docker support**

> This module is isolated and does not mix with the Next.js codebase.

---

## 1) Structure

```text
python-rt-agent-demo/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── README.md
├── src/
│   └── app/
│       ├── agents/
│       ├── agent_flow.py
│       ├── backend_listener.py
│       ├── config.py
│       ├── logging_config.py
│       ├── main.py
│       ├── models.py
│       ├── ms_agent_client.py
│       ├── pubsub_protocol.py
│       ├── pubsub_service.py
│       └── static/index.html
└── tests/
```

---

## 2) Prerequisites

- Python 3.11+
- UV installed ([https://docs.astral.sh/uv/](https://docs.astral.sh/uv/))
- An **Azure Web PubSub** resource
- **Microsoft Agent Framework** environment variables

---

## 3) Quick Start (Local)

### 3.1 Variables

1. Copy the template:

```bash
cp .env.example .env
```

2. Complete at least:

- `AZURE_WEBPUBSUB_CONNECTION_STRING`
- `AZURE_WEBPUBSUB_HUB_NAME`
- `AZURE_WEBPUBSUB_GROUP`

3. Complete Agent Framework settings:

- `AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME`

4. Choose an authentication method (without Azure CLI):

- **Mode A (Recommended for Docker): API key**
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_API_VERSION` (optional, recommended)

- **Mode B: Managed Identity / Service Principal via env vars**
  - `AZURE_AI_PROJECT_ENDPOINT`
  - `AZURE_TENANT_ID`
  - `AZURE_CLIENT_ID`
  - `AZURE_CLIENT_SECRET`

> This backend runs in strict mode with the Agent Framework. If these variables are missing, response processing will fail.

5. To enable Query-to-Insight over Azure SQL, add:

- `AZURE_SQL_CONNECTION_STRING`
- `SQL_QUERY_TIMEOUT_SECONDS` (default: `20`)
- `SQL_ROW_LIMIT` (default: `200`)
- `SQL_MAX_RETRY_CORRECTIONS` (default: `2`)

### 3.2 Install and Run with UV (Isolated)

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run uvicorn app.main:app --host 0.0.0.0 --port 8010 --app-dir src
```

Using this flow, everything remains encapsulated within the `.venv` inside `python-rt-agent-demo`.

Open in your browser:

- `http://localhost:8010`

---

## 4) Docker Configuration (Optional)

```bash
docker compose up --build
```

Open:

- `http://localhost:8010`

---

## 5) Deploying Image to Azure Web App for Containers (Simple Method)
```bash
# Change permissions for the deploy file
$ chmod +x simple-deploy.md

# Login to Azure via az CLI
$ az login --tenant <TENANT-ID> # or az login --use-device-code --tenant <TENANT_ID>

# Execute the script
$ ./simple-deploy.md
```
> **Recommendation:** In Azure, use managed secrets (Key Vault and/or Container Apps secrets) to avoid exposing the `AZURE_WEBPUBSUB_CONNECTION_STRING`.

---

## 6) How Real-Time Works

1. Frontend requests a token via `POST /api/negotiate`.
2. Frontend connects its WebSocket to the signed Web PubSub URL.
3. Frontend sends a `user.message` to the group.
4. Backend listener (also via WebSocket) consumes the message from the group.
5. `Planner` routes the request:
    - Analytical questions -> `Librarian -> SQL Coder -> SQL Execution -> Evaluator`.
    - General questions -> Chat response in `Evaluator`.
6. `SQL Execution` applies guardrails (`SELECT` only, DDL/DML blocking, forced `TOP`).
7. Backend publishes:
    - `status`
    - `assistant.delta` (token streaming)
    - `assistant.complete`

---

## 7) Quick API

- `GET /health`
- `GET /ready`
- `POST /api/negotiate`
- `POST /api/messages` (alternative backend->group)

---

## 8) Quality and Validation

### Tests

```bash
uv run pytest
```

### Linting

```bash
uv run ruff check src tests
```

### Phase 2 Benchmarks (A/B/C)

Run reproducible synthetic benchmarks and generate a report:

```bash
PYTHONPATH=src uv run python scripts/run_benchmarks.py --output reports/benchmark_results.json
PYTHONPATH=src uv run python scripts/generate_benchmark_report.py --input reports/benchmark_results.json --output reports/benchmark_report.md
```

Live Benchmark against Azure SQL (Phase 3):

```bash
PYTHONPATH=src uv run python scripts/run_benchmarks.py --mode live --output reports/benchmark_results_live.json
PYTHONPATH=src uv run python scripts/generate_benchmark_report.py --input reports/benchmark_results_live.json --output reports/benchmark_report_live.md
```

> Requires `AZURE_SQL_CONNECTION_STRING`. The live benchmark uses safe queries against `INFORMATION_SCHEMA`.

Benchmark test suite:

```bash
uv run pytest tests/benchmarks -q
```

---

## 9) Applied Security

- Input validation with Pydantic (`message`, IDs, enums).
- Secrets kept out of code (environment variables).
- No logging of sensitive keys.
- Access tokens with least-privilege roles (`joinLeaveGroup`, `sendToGroup`).
- Error handling and reconnection with backoff + jitter in the listener.

---

## 10) Recommended Enhancements (Production-Ready)

1. **Strong User Authentication**
    - Add JWT or an API Gateway in front of `/api/negotiate`.
    - **Reason:** Prevent unauthorized clients from requesting hub tokens.
2. **Rate Limiting and Quotas**
    - Limit `user.message` by user/IP.
    - **Reason:** Abuse mitigation and cost control.
3. **Persistence and Auditing**
    - Save envelopes and conversation states in a DB (PostgreSQL/Cosmos).
    - **Reason:** Traceability and recovery.
4. **Full Observability**
    - Metrics (latency per stage), distributed tracing, and alerting.
    - **Reason:** Operational support and SLO fulfillment.
5. **Idempotency via `correlation_id`**
    - Deduplicate events triggered by reconnections or retries.
    - **Reason:** Consistency in real-time flows.
6. **Agent Isolation via Interfaces**
    - Maintain step contracts and add contract tests per agent.
    - **Reason:** Improved extensibility and SOLID compliance.
7. **Payload Hardening**
    - Limit `payload` size, anti-injection validation, and sanitization.
    - **Reason:** Security and stability.

---

## 11) Troubleshooting

- **UV not installed**
    - Install it from the official Astral documentation and re-run `uv venv`.
- **Environment activation**
    - You can run everything directly with `uv run ...` without needing `source .venv/bin/activate`.
- **WebSocket connection failure**
    - Verify `AZURE_WEBPUBSUB_CONNECTION_STRING`, hub name, and group name.
- **Agent not responding**
    - Check the listener logs.
- **No LLM output**
    - Verify `AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME` and your auth method:
        - `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY`, OR
        - `AZURE_AI_PROJECT_ENDPOINT` + identity variables (`AZURE_TENANT_ID`, etc.).
