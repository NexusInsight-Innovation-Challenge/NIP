# Frontend Guide

Guía completa del frontend para configurar, ejecutar y mantener la interfaz realtime con Azure Web PubSub.

## 1) Resumen de arquitectura frontend

- Framework: Next.js 16 (App Router).
- Vista principal: `app/page.tsx`.
- UI system: componentes `components/ui` + Tailwind CSS v4.
- Realtime transport: WebSocket con subprotocolo `json.webpubsub.azure.v1`.
- Backend bridge: `/api/realtime/negotiate` y `/api/realtime/message`.

## 2) Variables de entorno

El frontend no consume secretos directamente. La app cliente usa endpoints del backend y este firma la conexión.

Variables requeridas en el servidor (archivo `.env.local`):

- `AZURE_WEBPUBSUB_CONNECTION_STRING`:
  - Conexión completa de Azure Web PubSub.
  - Ejemplo: `Endpoint=https://<service>.webpubsub.azure.com;AccessKey=<key>;Version=1.0;`
- `AZURE_WEBPUBSUB_HUB_NAME`:
  - Nombre del hub utilizado por la app.
  - Ejemplo: `agentshub`
- `AZURE_WEBPUBSUB_GROUP`:
  - Grupo compartido donde publican/suscriben frontend y backend.
  - Ejemplo: `realtime-agent-room`

### Regla de seguridad

- No usar `NEXT_PUBLIC_` para secretos.
- El cliente nunca debe recibir `connectionString` ni `accessKey`.

## 3) Configuración local

1. Instalar dependencias:

```bash
npm install
```

2. Crear entorno local:

```bash
cp .env.example .env.local
```

3. Configurar variables de Azure en `.env.local`.

4. Ejecutar app:

```bash
npm run dev
```

5. Abrir:

- `http://localhost:3000`

## 4) Flujo realtime del frontend

1. El usuario entra a la UI.
2. El frontend llama `POST /api/realtime/negotiate` con `sessionId`.
3. El backend devuelve URL firmada para WebSocket.
4. El frontend abre socket y hace `joinGroup`.
5. Al enviar mensaje, el frontend llama `POST /api/realtime/message`.
6. El backend emite eventos al grupo configurado por entorno.
7. El frontend renderiza tokens en streaming y cierra con `assistant-complete`.

## 5) Contratos de eventos que renderiza el frontend

Eventos esperados desde Web PubSub:

- `status`
  - `queued | processing | completed | error`
  - muestra estado operativo en la UI.
- `assistant-token`
  - token parcial para streaming visual.
- `assistant-complete`
  - contenido final y checkpoints del pipeline.

## 6) Archivos clave frontend

- `app/page.tsx`
  - Estado del chat y conexión websocket.
  - Manejo de `onopen`, `onmessage`, `onclose`, `onerror`.
  - Render de mensajes y estado de agentes.
- `app/globals.css`
  - Tokens de tema y estilos globales Tailwind.
- `components/ui/*`
  - Primitivas visuales (Button, Card, Badge, Textarea, ScrollArea).

## 7) Checklist de validación frontend

- [ ] `npm run dev` inicia sin errores.
- [ ] El badge cambia a conectado.
- [ ] Al enviar prompt se visualiza mensaje del usuario.
- [ ] Se reciben tokens en vivo (`assistant-token`).
- [ ] El estado finaliza en completado.
- [ ] No hay secretos en el bundle del cliente.

## 8) Troubleshooting frontend

### La app no inicia

- Verificar versión Node (recomendado 20+).
- Ejecutar `npm install` de nuevo.
- Revisar errores de sintaxis en `.env.local`.

### El socket no conecta

- Revisar que `AZURE_WEBPUBSUB_CONNECTION_STRING`, `AZURE_WEBPUBSUB_HUB_NAME` y `AZURE_WEBPUBSUB_GROUP` sean válidos.
- Confirmar que el hub existe en Azure.
- Revisar pestaña Network para respuesta de `/api/realtime/negotiate`.

### No hay respuesta del agente

- Revisar respuesta de `/api/realtime/message`.
- Validar que la sesión cumple el formato permitido (`[a-zA-Z0-9_-]{6,80}`).
- Confirmar que el backend publica eventos al grupo correcto.

## 9) Buenas prácticas de frontend para este proyecto

- Mantener `app/page.tsx` centrado en orquestación UI y estado.
- Mover lógica compleja a módulos de `lib/*`.
- Tipar todos los payloads de red y eventos.
- Evitar render bloqueante: preferir streaming incremental.
- Eliminar código muerto y mocks no usados cuando se migra funcionalidad.
