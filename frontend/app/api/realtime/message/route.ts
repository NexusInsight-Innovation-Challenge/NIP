import { NextResponse } from "next/server";
import { z } from "zod";
import { publishRealtimeEvent } from "@/lib/realtime/service";
import { appendMessage, upsertSession } from "@/lib/realtime/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const bodySchema = z.object({
  sessionId: z.string().regex(/^[a-zA-Z0-9_-]{6,80}$/),
  text: z.string().trim().min(1).max(4000),
  locale: z.string().default("es").optional(),
});

export async function POST(request: Request) {
  try {
    const payload = bodySchema.parse(await request.json());
    const now = new Date().toISOString();
    const userId = `web-user-${payload.sessionId.slice(0, 12)}`;

    const envelope = {
      event_type: "user.message",
      id: crypto.randomUUID(),
      correlation_id: crypto.randomUUID(),
      conversation_id: payload.sessionId,
      timestamp: now,
      role: "user",
      payload: {
        message: payload.text,
        locale: payload.locale,
        userId,
      },
      metadata: {
        source: "next.realtime-api",
      },
    };

    await publishRealtimeEvent(envelope);
    await upsertSession(payload.sessionId, userId);
    await appendMessage(payload.sessionId, {
      content: payload.text,
      id: envelope.id,
      role: "user",
      source: "next.realtime-api",
      timestamp: now,
    });

    return NextResponse.json({ ok: true }, { status: 202 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request";

    return NextResponse.json(
      {
        error: "No se pudo procesar el mensaje.",
        detail: process.env.NODE_ENV === "development" ? message : undefined,
      },
      { status: 400 },
    );
  }
}
