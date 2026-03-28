import { NextResponse } from "next/server";
import { z } from "zod";
import { negotiateRealtimeConnection } from "@/lib/realtime/service";
import { upsertSession } from "@/lib/realtime/store";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

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
  console.log("[NEGOTIATE] Inicia petición de negotiate");
  try {
    // 1. Verificamos la sesión a nivel de servidor
    const session = await getServerSession(authOptions);
    if (!session) {
      console.warn("[NEGOTIATE] No hay sesión de servidor, retornando 401");
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const payload = bodySchema.parse(await request.json());
    
    // 2. Extraemos el email real devuelto por Entra ID (si existe), si no, usamos fallback
    const validatedUserEmail = session?.user?.email ?? "unknown-user";
    const userId = payload.userId ?? validatedUserEmail;

    console.log(`[NEGOTIATE] Procesando sessionId: ${payload.sessionId}, userId: ${userId}`);

    console.log("[NEGOTIATE] Insertando sesión en Redis...");
    await upsertSession(payload.sessionId, userId);
    
    console.log("[NEGOTIATE] Solicitando token a Azure Web PubSub...");
    const token = await negotiateRealtimeConnection(userId);

    console.log("[NEGOTIATE] Token obtenido exitosamente");
    return NextResponse.json(token, { status: 200 });
  } catch (error) {
    console.error("[NEGOTIATE ERROR]", error);
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
