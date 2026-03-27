import { NextResponse } from "next/server";
import { z } from "zod";
import { publishRealtimeEvent } from "@/lib/realtime/service";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const bodySchema = z.object({
  sessionId: z.string().regex(/^[a-zA-Z0-9_-]{6,80}$/),
  correlationId: z.string().trim().min(8).max(120),
  approved: z.boolean(),
  reason: z.string().trim().max(800).optional(),
  decidedBy: z.string().trim().min(3).max(80).optional(),
});

export async function POST(request: Request) {
  try {
    const payload = bodySchema.parse(await request.json());
    const now = new Date().toISOString();

    const envelope = {
      event_type: "approval.response",
      id: crypto.randomUUID(),
      correlation_id: payload.correlationId,
      conversation_id: payload.sessionId,
      timestamp: now,
      role: "user",
      payload: {
        approved: payload.approved,
        reason: payload.reason,
        decided_by:
          payload.decidedBy ?? `web-user-${payload.sessionId.slice(0, 12)}`,
      },
      metadata: {
        source: "next.realtime-approval",
      },
    };

    await publishRealtimeEvent(envelope);
    return NextResponse.json({ ok: true }, { status: 202 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request";

    return NextResponse.json(
      {
        error: "No se pudo registrar la decisión de aprobación.",
        detail: process.env.NODE_ENV === "development" ? message : undefined,
      },
      { status: 400 },
    );
  }
}
