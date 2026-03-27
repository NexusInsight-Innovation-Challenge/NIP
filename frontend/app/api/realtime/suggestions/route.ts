import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_SUGGESTIONS = [
  "Dame un reporte ejecutivo con KPIs clave de la base de datos",
  "Top 10 productos por ventas y participación",
  "Tendencia mensual de ventas con alertas de caída",
  "Clientes con mayor contribución y concentración de riesgo",
];

const parseLimit = (raw: string | null): number => {
  const parsed = Number.parseInt(raw ?? "6", 10);
  if (Number.isNaN(parsed)) {
    return 6;
  }
  return Math.min(Math.max(parsed, 1), 12);
};

export async function GET(request: Request) {
  const url = new URL(request.url);
  const limit = parseLimit(url.searchParams.get("limit"));
  const backendBaseUrl =
    process.env.PYTHON_RT_AGENT_BASE_URL?.replace(/\/$/, "") ||
    "http://localhost:8010";

  try {
    const response = await fetch(
      `${backendBaseUrl}/api/sql/suggestions?limit=${limit}`,
      {
        method: "GET",
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error("Backend suggestions endpoint failed");
    }

    const payload = (await response.json()) as {
      suggestions?: string[];
      source?: string;
      tableCount?: number;
    };

    return NextResponse.json(
      {
        source: payload.source ?? "backend",
        suggestions: (payload.suggestions ?? []).slice(0, limit),
        tableCount: payload.tableCount ?? 0,
      },
      { status: 200 },
    );
  } catch {
    return NextResponse.json(
      {
        source: "fallback",
        suggestions: DEFAULT_SUGGESTIONS.slice(0, limit),
        tableCount: 0,
      },
      { status: 200 },
    );
  }
}
