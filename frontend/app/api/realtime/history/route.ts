import { NextResponse } from "next/server";
import { z } from "zod";
import {
  appendMessage,
  clearSessionHistory,
  getMessages,
  upsertSession,
  type PersistedChatMessage,
} from "@/lib/realtime/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const sessionSchema = z.string().regex(/^[a-zA-Z0-9_-]{6,80}$/);

const postBodySchema = z.object({
  content: z.string().trim().min(1).max(12_000),
  id: z.string().optional(),
  role: z.enum(["assistant", "system"]),
  sessionId: sessionSchema,
  source: z.string().trim().min(1).max(120).default("next.client"),
  timestamp: z.string().datetime().optional(),
  userId: z.string().trim().min(3).max(80).optional(),
});

export async function GET(request: Request) {
  const url = new URL(request.url);
  const rawSessionId = url.searchParams.get("sessionId");

  if (!rawSessionId) {
    return NextResponse.json(
      { error: "sessionId is required" },
      { status: 400 },
    );
  }

  const parsedSessionId = sessionSchema.safeParse(rawSessionId);
  if (!parsedSessionId.success) {
    return NextResponse.json({ error: "Invalid sessionId" }, { status: 400 });
  }

  const limitParam = Number.parseInt(
    url.searchParams.get("limit") ?? "200",
    10,
  );
  const limit = Number.isNaN(limitParam)
    ? 200
    : Math.min(Math.max(limitParam, 1), 500);

  try {
    console.log(`[HISTORY-GET] Obteniendo historial para sessionId: ${parsedSessionId.data}, limit: ${limit}`);
    const messages = await getMessages(parsedSessionId.data, limit);
    console.log(`[HISTORY-GET] ${messages.length} mensajes obtenidos exitosamente.`);
    return NextResponse.json({ messages }, { status: 200 });
  } catch (error) {
    console.error("[HISTORY-GET ERROR] Falla al obtener mensajes:", error);
    const detail = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      {
        error: "No se pudo recuperar el historial.",
        detail: process.env.NODE_ENV === "development" ? detail : undefined,
      },
      { status: 500 },
    );
  }
}

export async function POST(request: Request) {
  try {
    const payload = postBodySchema.parse(await request.json());
    const timestamp = payload.timestamp ?? new Date().toISOString();
    const message: PersistedChatMessage = {
      content: payload.content,
      id: payload.id ?? crypto.randomUUID(),
      role: payload.role,
      source: payload.source,
      timestamp,
    };

    const userId =
      payload.userId ?? `web-user-${payload.sessionId.slice(0, 12)}`;
        
      console.log(`[HISTORY-POST] Guardando mensaje de ${message.role} para sessionId: ${payload.sessionId}`);
      await upsertSession(payload.sessionId, userId);
      await appendMessage(payload.sessionId, message);
      
      console.log(`[HISTORY-POST] Mensaje persistido exitosamente en Redis`);
      return NextResponse.json({ ok: true }, { status: 201 });
    } catch (error) {
      console.error("[HISTORY-POST ERROR] Fallo al guardar en base de datos:", error);
    const detail = error instanceof Error ? error.message : "Invalid request";
    return NextResponse.json(
      {
        error: "No se pudo guardar el historial.",
        detail: process.env.NODE_ENV === "development" ? detail : undefined,
      },
      { status: 400 },
    );
  }
}

export async function DELETE(request: Request) {
  const url = new URL(request.url);
  const rawSessionId = url.searchParams.get("sessionId");

  if (!rawSessionId) {
    return NextResponse.json(
      { error: "sessionId is required" },
      { status: 400 },
    );
  }

  const parsedSessionId = sessionSchema.safeParse(rawSessionId);
  if (!parsedSessionId.success) {
    return NextResponse.json({ error: "Invalid sessionId" }, { status: 400 });
  }

  try {
    await clearSessionHistory(parsedSessionId.data);
    return NextResponse.json({ ok: true }, { status: 200 });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      {
        error: "No se pudo limpiar el historial.",
        detail: process.env.NODE_ENV === "development" ? detail : undefined,
      },
      { status: 500 },
    );
  }
}
