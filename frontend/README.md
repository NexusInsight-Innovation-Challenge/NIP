# Innovation Challenge Chat | Azure Web PubSub + Next.js

Interfaz visual de chat en tiempo real con pipeline de agentes y backend en Next.js App Router.

## Documentación

- Guía frontend completa: `docs/FRONTEND.md`
- Configuración rápida de entorno: `.env.example`
- Docker y despliegue Azure: sección Docker de este README
- Despliegue con `azd up`: sección AZD de este README

## Stack

- Next.js 16 (App Router)
- React 19 + Tailwind CSS v4
- Azure Web PubSub (`@azure/web-pubsub`)
- Redis 7 (persistencia de sesiones e historial)
- Arquitectura por capas (`lib/agents`, `lib/realtime`, `app/api`)

## Requisitos

- Node.js 20+
- Una instancia de Azure Web PubSub

## Variables de entorno

1. Copia `.env.example` según el modo de ejecución:

```bash
# desarrollo local con Next
cp .env.example .env.local

# Docker Compose (dev/prod)
cp .env.example .env
```

2. Configura:

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

> Nunca expongas secretos con prefijos `NEXT_PUBLIC_`.

## Ejecutar local

```bash
npm install
npm run dev
```

Abre `http://localhost:3000`.

## Docker

El proyecto incluye soporte Docker para desarrollo y producción con imágenes listas para Azure Containers.

Archivos incluidos:

- `Dockerfile` (multi-stage: `dev`, `builder`, `runner`)
- `docker-compose.dev.yml`
- `docker-compose.prod.yml`
- `.dockerignore`

> Ambos compose incluyen servicio `redis` con AOF habilitado y volumen persistente.

### Docker en modo desarrollo

```bash
docker compose -f docker-compose.dev.yml up --build
```

- Hot reload activo.
- Puerto expuesto: `3000`.
- Usa variables desde `.env`.

### Docker en modo producción

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

- Ejecuta imagen optimizada con salida Next standalone.
- Puerto expuesto: `3000`.
- Reinicio automático (`unless-stopped`).

### Build y run manual (sin compose)

Desarrollo:

```bash
docker build --target dev -t innovation-chat:dev .
docker run --rm -it -p 3000:3000 --env-file .env innovation-chat:dev
```

Producción:

```bash
docker build --target runner -t innovation-chat:prod .
docker run --rm -it -p 3000:3000 --env-file .env innovation-chat:prod
```

## Despliegue en Azure Containers

La imagen está preparada para ejecutar en `PORT=3000` y `HOSTNAME=0.0.0.0`.

### Opción recomendada: Azure Container Apps

1. Construye y publica la imagen en Azure Container Registry (ACR):

```bash
az acr build \
	--registry <ACR_NAME> \
	--image innovation-chat:latest \
	.
```

2. Crea o actualiza la app con la imagen y variables de entorno:

```bash
az containerapp up \
	--name innovation-chat \
	--resource-group <RESOURCE_GROUP> \
	--environment <CONTAINER_APPS_ENV> \
	--image <ACR_NAME>.azurecr.io/innovation-chat:latest \
	--target-port 3000 \
	--ingress external \
	--env-vars \
		AZURE_WEBPUBSUB_CONNECTION_STRING="<VALUE>" \
		AZURE_WEBPUBSUB_HUB_NAME="agentshub" \
		AZURE_WEBPUBSUB_GROUP="realtime-agent-room" \
		NODE_ENV="production"
```

### Opción simple: Azure Container Instances (ACI)

```bash
az container create \
	--resource-group <RESOURCE_GROUP> \
	--name innovation-chat \
	--image <ACR_NAME>.azurecr.io/innovation-chat:latest \
	--registry-login-server <ACR_NAME>.azurecr.io \
	--registry-username <ACR_USERNAME> \
	--registry-password <ACR_PASSWORD> \
	--dns-name-label <UNIQUE_DNS_LABEL> \
	--ports 3000 \
	--environment-variables \
		AZURE_WEBPUBSUB_CONNECTION_STRING="<VALUE>" \
		AZURE_WEBPUBSUB_HUB_NAME="agentshub" \
		AZURE_WEBPUBSUB_GROUP="realtime-agent-room" \
		NODE_ENV="production"
```

> Recomendación: en Azure usa secretos gestionados (Key Vault o secrets de Container Apps) para no exponer `AZURE_WEBPUBSUB_CONNECTION_STRING`.

## AZD (Azure Developer CLI)

El repositorio ya incluye soporte para `azd`:

- `azure.yaml`
- `infra/main.bicep`
- `infra/main.parameters.json`

### Requisitos

- Azure CLI (`az`)
- Azure Developer CLI (`azd`)
- Suscripción activa en Azure

### Primer despliegue

1. Login:

```bash
az login
azd auth login
```

2. Inicializar entorno azd:

```bash
azd init
azd env new dev
```

3. Configurar variables requeridas por infraestructura:

```bash
azd env set AZURE_WEBPUBSUB_CONNECTION_STRING "<VALUE>"
azd env set AZURE_WEBPUBSUB_HUB_NAME "agentshub"
azd env set AZURE_WEBPUBSUB_GROUP "realtime-agent-room"
```

4. Desplegar todo (infra + app):

```bash
azd up
```

### Deploy posteriores

Para publicar cambios de app sin recrear toda la infraestructura:

```bash
azd deploy
```

Para volver a provisionar infraestructura:

```bash
azd provision
```

## Endpoints

- `POST /api/realtime/negotiate`: negocia URL WebSocket firmada para la sesión.
- `POST /api/realtime/message`: ejecuta pipeline de agentes y publica eventos realtime en Azure Web PubSub.
- `GET /api/realtime/history?sessionId=...`: recupera historial persistido de la sesión.
- `POST /api/realtime/history`: persiste mensajes assistant/system emitidos en cliente.
- `POST /api/chat`: endpoint legacy deshabilitado (`410`) para evitar comportamiento inconsistente.

## Frontend rápido

- UI principal en `app/page.tsx`.
- Conexión WebSocket con subprotocolo `json.webpubsub.azure.v1`.
- Estados de conexión en vivo: disconnected, connecting, connected.
- Render incremental por eventos `assistant-token`.
- Cierre de flujo con evento `assistant-complete`.

## Flujo realtime

1. Frontend solicita token en `/api/realtime/negotiate`.
2. Frontend abre WebSocket a Azure Web PubSub con subprotocolo `json.webpubsub.azure.v1`.
3. Frontend envía mensaje al backend por `/api/realtime/message`.
4. Backend ejecuta agentes y publica eventos (`status`, `assistant-token`, `assistant-complete`) al grupo de sesión.
5. Frontend renderiza streaming en vivo.
6. Mensajes se persisten en Redis para recuperación de chat y continuidad de sesión.

## Calidad y seguridad

- Validación estricta de payloads con `zod`.
- Secrets solo en servidor; nunca se exponen en cliente.
- sessionId/userId restringidos por regex para reducir abuso e inyección.
- Mensajes de error sanitizados en producción.
- Código muerto removido y separación clara de responsabilidades.

## Troubleshooting básico

- Si `npm run dev` falla, verifica primero `.env.local` y valores de Azure Web PubSub.
- Si la UI abre pero no conecta, revisa que el hub coincida con `AZURE_WEBPUBSUB_HUB_NAME`.
- Revisa también que frontend y backend compartan el mismo `AZURE_WEBPUBSUB_GROUP`.
- Si no llega respuesta del agente, valida en Network las rutas `/api/realtime/negotiate` y `/api/realtime/message`.
