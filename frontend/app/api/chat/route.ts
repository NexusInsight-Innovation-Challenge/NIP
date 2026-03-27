import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST() {
  return NextResponse.json(
    {
      error: "Este endpoint fue reemplazado por /api/realtime/message.",
      migration: {
        negotiate: "/api/realtime/negotiate",
        message: "/api/realtime/message",
      },
    },
    { status: 410 },
  );
}
