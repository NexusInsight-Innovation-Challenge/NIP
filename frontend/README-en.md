[Spanish version](./README.md)
# Innovation Challenge Chat | Azure Web PubSub + Next.js

Real-time chat visual interface featuring an agent pipeline and a Next.js App Router backend.

## Documentation

- Full frontend guide: `docs/FRONTEND.md`
- Quick environment setup: `.env.example`
- Docker and Azure deployment: See the **Docker** section of this README
- Deployment with `azd up`: See the **AZD** section of this README

## Stack

- Next.js 16 (App Router)
- React 19 + Tailwind CSS v4
- Azure Web PubSub (`@azure/web-pubsub`)
- Redis 7 (Session persistence and history)
- Layered Architecture (`lib/agents`, `lib/realtime`, `app/api`)

## Prerequisites

- Node.js 20+
- An Azure Web PubSub instance

## Environment Variables

1. Copy `.env.example` based on your execution mode:

```bash
# Local development with Next
cp .env.example .env.local

# Docker Compose (dev/prod)
cp .env.example .env
```

2. Configure:

```bash
AZURE_WEBPUBSUB_CONNECTION_STRING=Endpoint=...;AccessKey=...;Version=1.0;
AZURE_WEBPUBSUB_HUB_NAME=agentshub
AZURE_WEBPUBSUB_GROUP=realtime-agent-room
REDIS_URL=redis://redis:6379
REDIS_CHAT_TTL_SECONDS=604800
REDIS_CHAT_MAX_MESSAGES=500
NODE_ENV=production
PORT=3000
HOSTNAME=0.0.0.0
NEXT_TELEMETRY_DISABLED=1
```

> **Warning:** Never expose secrets using `NEXT_PUBLIC_` prefixes.

## Running Locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Docker

This project includes Docker support for both development and production with images ready for Azure Container Apps/Web Apps.

Included files:

- `Dockerfile` (multi-stage: `dev`, `builder`, `runner`)
- `docker-compose.dev.yml`
- `docker-compose.prod.yml`
- `.dockerignore`

> Both compose files include a `redis` service with AOF enabled and a persistent volume.

### Docker in Development Mode

```bash
docker compose -f docker-compose.dev.yml up --build
```

- Hot reload active.
- Exposed port: `3000`.
- Uses variables from `.env`.

### Docker in Production Mode

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

- Runs an optimized image with Next.js standalone output.
- Exposed port: `3000`.
- Automatic restart (`unless-stopped`).

### Manual Build and Run (without Compose)

Development:

```bash
docker build --target dev -t innovation-chat:dev .
docker run --rm -it -p 3000:3000 --env-file .env innovation-chat:dev
```

Production:

```bash
docker build --target runner -t innovation-chat:prod .
docker run --rm -it -p 3000:3000 --env-file .env innovation-chat:prod
```

### Simple Deployment to Azure Web App for Containers
```bash
# Change mode for the deployment script
$ chmod +x simple-deploy.md

# Login to Azure via az CLI
$ az login --tenant <TENANT-ID> # or az login --use-device-code --tenant <TENANT_ID>

# Execute the script
$ ./simple-deploy.md
```

> **Recommendation:** In Azure, use managed secrets (Key Vault and/or Container Apps secrets) to avoid exposing the `AZURE_WEBPUBSUB_CONNECTION_STRING`.

## AZD (Azure Developer CLI)

The repository includes native `azd` support:

- `azure.yaml`
- `infra/main.bicep`
- `infra/main.parameters.json`

### Prerequisites

- Azure CLI (`az`)
- Azure Developer CLI (`azd`)
- An active Azure subscription

### Initial Deployment

1. Login:

```bash
az login
azd auth login
```

2. Initialize the azd environment:

```bash
azd init
azd env new dev
```

3. Configure required infrastructure variables:

```bash
azd env set AZURE_WEBPUBSUB_CONNECTION_STRING "<VALUE>"
azd env set AZURE_WEBPUBSUB_HUB_NAME "agentshub"
azd env set AZURE_WEBPUBSUB_GROUP "realtime-agent-room"
```

4. Deploy everything (infra + app):

```bash
azd up
```

### Subsequent Deploys

To publish app changes without recreating the entire infrastructure:

```bash
azd deploy
```

To re-provision infrastructure:

```bash
azd provision
```

## Endpoints

- `POST /api/realtime/negotiate`: Negotiates a signed WebSocket URL for the session.
- `POST /api/realtime/message`: Executes the agent pipeline and publishes real-time events to Azure Web PubSub.
- `GET /api/realtime/history?sessionId=...`: Retrieves persisted session history.
- `POST /api/realtime/history`: Persists assistant/system messages emitted from the client.
- `POST /api/chat`: Legacy endpoint disabled (`410`) to prevent inconsistent behavior.

## Frontend Quick Look

- Main UI located in `app/page.tsx`.
- WebSocket connection using the `json.webpubsub.azure.v1` subprotocol.
- Live connection states: `disconnected`, `connecting`, `connected`.
- Incremental rendering via `assistant-token` events.
- Stream completion via `assistant-complete` event.

## Real-time Flow

1. Frontend requests a token from `/api/realtime/negotiate`.
2. Frontend opens a WebSocket to Azure Web PubSub using the `json.webpubsub.azure.v1` subprotocol.
3. Frontend sends a message to the backend via `/api/realtime/message`.
4. Backend executes agents and publishes events (`status`, `assistant-token`, `assistant-complete`) to the session group.
5. Frontend renders the live stream.
6. Messages are persisted in Redis for chat recovery and session continuity.

## Quality and Security

- Strict payload validation using `zod`.
- Secrets are server-side only; never exposed to the client.
- `sessionId`/`userId` restricted by regex to mitigate abuse and injection.
- Sanitized error messages in production.
- Removed dead code and clear separation of concerns.

## Basic Troubleshooting

- If `npm run dev` fails, first check `.env.local` and your Azure Web PubSub values.
- If the UI opens but fails to connect, ensure the hub name matches `AZURE_WEBPUBSUB_HUB_NAME`.
- Verify that both the frontend and backend share the same `AZURE_WEBPUBSUB_GROUP`.
- If no agent response is received, check the Network tab for the `/api/realtime/negotiate` and `/api/realtime/message` routes.
