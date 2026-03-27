import { NextResponse } from "next/server";
import { z } from "zod";
import { negotiateRealtimeConnection } from "@/lib/realtime/service";
import { upsertSession } from "@/lib/realtime/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const bodySchema = z.object({
  sessionId: z.string().regex(/^[a-zA-Z0-9_-]{6,80}$/),
  userId: z
    .string()
    .regex(/^[a-zA-Z0-9_-]{3,80}$/)
    .optional(),
});

export async function POST(request: Request) {
  try {
    const payload = bodySchema.parse(await request.json());
    const userId =
      payload.userId ?? `web-user-${payload.sessionId.slice(0, 12)}`;

    await upsertSession(payload.sessionId, userId);
    const token = await negotiateRealtimeConnection(userId);

    return NextResponse.json(token, { status: 200 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request";

    return NextResponse.json(
      {
        error: "No se pudo negociar conexión realtime.",
        detail: process.env.NODE_ENV === "development" ? message : undefined,
      },
      { status: 400 },
    );
  }
}
