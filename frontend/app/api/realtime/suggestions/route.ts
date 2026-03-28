import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_SUGGESTIONS = [
  "Give me an executive report with key KPIs from the database",
  "Top 10 products by sales and market share",
  "Monthly sales trend with decline alerts",
  "Customers with highest contribution and risk concentration",
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
