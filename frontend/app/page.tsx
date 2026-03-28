"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { nanoid } from "nanoid";
import { useSession } from "next-auth/react";
import { toast } from "sonner";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  ModelSelectorLogo,
  ModelSelectorName,
} from "@/components/ai-elements/model-selector";
import type { PromptInputMessage } from "@/components/ai-elements/prompt-input";
import {
  PromptInput,
  PromptInputBody,
  PromptInputButton,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from "@/components/ai-elements/prompt-input";
import {
  PipelineVisualization,
  ExecutionTimeline,
  TransparencyPanel,
} from "@/components/ai-elements/pipeline-viz";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { NexusLogo } from "@/components/nexus-logo";
import {
  RefreshCwIcon,
  SparklesIcon,
  WifiIcon,
  WifiOffIcon,
  ZapIcon,
  PrinterIcon,
} from "lucide-react";
import {
  RealtimeNegotiateResponse,
  RealtimeServerEvent,
} from "@/lib/realtime/contracts";

type ChatRole = "user" | "assistant";

interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
}

interface PersistedChatMessageResponse {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
}

interface StartupSuggestionsResponse {
  suggestions?: string[];
  source?: string;
  tableCount?: number;
}

type SocketStatus = "disconnected" | "connecting" | "connected";
type PipelineRoute = "sql_pipeline" | "chat_pipeline" | "general";
type PipelineStageState = "idle" | "running" | "completed" | "error";

interface TransparencySnapshot {
  analysisQuestion?: string;
  generatedSql?: string;
  validatedSql?: string;
  rowsReturned?: number;
  sqlRetries?: number;
  sqlExecutionMs?: number;
  sqlLastResortFallback?: boolean;
  sqlLastError?: string;
  schemaSource?: string;
  schemaTablesCount?: number;
  schemaCatalogMissing?: boolean;
  stageTiming?: string;
  resultPreview?: string;
  // v2 fields
  subQueryCount?: number;
  subQueriesExecuted?: number;
  subQueriesFailed?: number;
  criticValidated?: boolean;
  approvalRequired?: boolean;
  approvalStatus?: string;
  approvalReason?: string;
  approvalCategories?: string;
  approvalRiskLevel?: string;
  approvalPolicyVersion?: string;
  approvalRequestedAt?: string;
  approvalTimeoutSeconds?: number;
  approvalDecidedAt?: string;
  approvalDecidedBy?: string;
  approvalDecisionReason?: string;
}

interface PendingApprovalState {
  correlationId: string;
  message: string;
  reason?: string;
  categories: string[];
  riskLevel?: string;
  timeoutSeconds: number;
  requestedAt?: string;
  expiresAt?: string;
  analysisQuestion?: string;
  validatedSql?: string;
}

const SOCKET_RETRY_MS = 1200;
const SESSION_STORAGE_KEY = "realtime-chat-session-id";

import { LogoutButton } from "@/components/logout-button";

const FIXED_MODEL = {
  chefSlug: "openai" as const,
  id: "gpt-4o",
  name: "GPT-4o",
};

const INITIAL_ASSISTANT_CONTENT =
  "System ready. This interface uses Azure Web PubSub for real-time messaging with an agent-based backend.";

const parseWebPubSubPayload = (event: MessageEvent<string>): unknown | null => {
  try {
    const parsed = JSON.parse(event.data) as {
      type?: string;
      data?: unknown;
    };

    if (parsed.type !== "message") {
      return null;
    }

    if (!parsed.data || typeof parsed.data !== "object") {
      return null;
    }

    return parsed.data;
  } catch {
    return null;
  }
};

const formatCloseDetail = (event: CloseEvent): string =>
  event.reason ? `${event.code} ${event.reason}` : String(event.code);

const normalizeStatusLabel = (status: RealtimeServerEvent): string => {
  if (status.type !== "status") {
    return "No activity";
  }

  return status.message ?? status.status;
};

const buildCheckpoints = (intent?: string, route?: string): string[] => {
  if (route === "sql_pipeline" || intent === "analytics") {
    return ["Planner", "Librarian", "SQL Coder", "Critic", "Evaluator"];
  }

  return ["Planner", "Evaluator"];
};

const getObjectField = (
  source: Record<string, unknown> | undefined,
  key: string,
): Record<string, unknown> | undefined => {
  const candidate = source?.[key];
  if (!candidate || typeof candidate !== "object") {
    return undefined;
  }

  return candidate as Record<string, unknown>;
};

const resolveString = (...candidates: unknown[]): string | undefined => {
  for (const candidate of candidates) {
    if (typeof candidate !== "string") {
      continue;
    }

    const trimmed = candidate.trim();
    if (trimmed) {
      return trimmed;
    }
  }

  return undefined;
};

const resolveNumber = (...candidates: unknown[]): number | undefined => {
  for (const candidate of candidates) {
    if (typeof candidate === "number" && Number.isFinite(candidate)) {
      return candidate;
    }

    if (typeof candidate !== "string") {
      continue;
    }

    const trimmed = candidate.trim();
    if (!trimmed) {
      continue;
    }

    const parsed = Number(trimmed);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return undefined;
};

const resolveBoolean = (...candidates: unknown[]): boolean | undefined => {
  for (const candidate of candidates) {
    if (typeof candidate === "boolean") {
      return candidate;
    }

    if (typeof candidate !== "string") {
      continue;
    }

    const normalized = candidate.trim().toLowerCase();
    if (normalized === "true") {
      return true;
    }

    if (normalized === "false") {
      return false;
    }
  }

  return undefined;
};

const resolveStringArray = (...candidates: unknown[]): string[] | undefined => {
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      const values = candidate
        .map((value) => (typeof value === "string" ? value.trim() : ""))
        .filter(Boolean);
      if (values.length > 0) {
        return values;
      }
      continue;
    }

    if (typeof candidate === "string") {
      const values = candidate
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
      if (values.length > 0) {
        return values;
      }
    }
  }

  return undefined;
};

const normalizeRealtimeEvent = (
  payload: unknown,
): RealtimeServerEvent | null => {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const event = payload as Record<string, unknown>;

  if (
    event.type === "status" ||
    event.type === "assistant-token" ||
    event.type === "assistant-complete" ||
    event.type === "approval-required" ||
    event.type === "approval-finalized"
  ) {
    return event as RealtimeServerEvent;
  }

  const eventType =
    typeof event.event_type === "string" ? event.event_type : undefined;
  const rawPayload =
    event.payload && typeof event.payload === "object"
      ? (event.payload as Record<string, unknown>)
      : undefined;
  const rawMetadata =
    event.metadata && typeof event.metadata === "object"
      ? (event.metadata as Record<string, unknown>)
      : undefined;
  const timestamp =
    typeof event.timestamp === "string"
      ? event.timestamp
      : new Date().toISOString();

  if (eventType === "status") {
    const status =
      typeof rawPayload?.status === "string" ? rawPayload.status : "processing";
    const message =
      typeof rawPayload?.message === "string" ? rawPayload.message : undefined;

    if (
      status === "queued" ||
      status === "processing" ||
      status === "completed" ||
      status === "error"
    ) {
      return {
        type: "status",
        status,
        message,
        timestamp,
      };
    }

    return null;
  }

  if (eventType === "assistant.delta") {
    const token = typeof rawPayload?.delta === "string" ? rawPayload.delta : "";

    return {
      type: "assistant-token",
      token,
      timestamp,
    };
  }

  if (eventType === "assistant.complete") {
    const transparency = getObjectField(rawPayload, "transparency");
    const content =
      typeof rawPayload?.message === "string" ? rawPayload.message : "";
    const intent = resolveString(rawMetadata?.intent, rawPayload?.intent);
    const route = resolveString(rawMetadata?.route, rawPayload?.route);
    const processingMs = resolveNumber(
      rawMetadata?.processing_ms,
      rawPayload?.processing_ms,
    );
    const analysisQuestion = resolveString(
      rawMetadata?.analysis_question,
      transparency?.analysis_question,
      rawPayload?.analysis_question,
    );
    const generatedSql = resolveString(
      rawMetadata?.generated_sql,
      transparency?.generated_sql,
      rawPayload?.generated_sql,
    );
    const validatedSql = resolveString(
      rawMetadata?.validated_sql,
      transparency?.validated_sql,
      rawPayload?.validated_sql,
    );
    const rowsReturned = resolveNumber(
      rawMetadata?.rows_returned,
      transparency?.rows_returned,
      rawPayload?.rows_returned,
    );
    const sqlRetries = resolveNumber(
      rawMetadata?.sql_retries,
      transparency?.sql_retries,
      rawPayload?.sql_retries,
    );
    const sqlExecutionMs = resolveNumber(
      rawMetadata?.sql_execution_ms,
      transparency?.sql_execution_ms,
      rawPayload?.sql_execution_ms,
    );
    const sqlLastResortFallback = resolveBoolean(
      rawMetadata?.sql_last_resort_fallback,
      transparency?.sql_last_resort_fallback,
      rawPayload?.sql_last_resort_fallback,
    );
    const sqlLastError = resolveString(
      rawMetadata?.sql_last_error,
      transparency?.sql_last_error,
      rawPayload?.sql_last_error,
    );
    const schemaSource = resolveString(
      rawMetadata?.schema_source,
      transparency?.schema_source,
      rawPayload?.schema_source,
    );
    const schemaTablesCount = resolveNumber(
      rawMetadata?.schema_tables_count,
      transparency?.schema_tables_count,
      rawPayload?.schema_tables_count,
    );
    const schemaCatalogMissing = resolveBoolean(
      rawMetadata?.schema_catalog_missing,
      transparency?.schema_catalog_missing,
      rawPayload?.schema_catalog_missing,
    );
    const stageTiming = resolveString(
      rawMetadata?.stage_timing,
      transparency?.stage_timing,
      rawPayload?.stage_timing,
    );
    const resultPreview = resolveString(
      rawMetadata?.result_preview,
      transparency?.result_preview,
      rawPayload?.result_preview,
    );
    const subQueryCount = resolveNumber(
      rawMetadata?.sub_query_count,
      transparency?.sub_query_count,
      rawPayload?.sub_query_count,
    );
    const subQueriesExecuted = resolveNumber(
      rawMetadata?.sub_queries_executed,
      transparency?.sub_queries_executed,
      rawPayload?.sub_queries_executed,
    );
    const subQueriesFailed = resolveNumber(
      rawMetadata?.sub_queries_failed,
      transparency?.sub_queries_failed,
      rawPayload?.sub_queries_failed,
    );
    const criticValidated = resolveBoolean(
      rawMetadata?.critic_validated,
      transparency?.critic_validated,
      rawPayload?.critic_validated,
    );
    const approvalRequired = resolveBoolean(
      rawMetadata?.approval_required,
      transparency?.approval_required,
      rawPayload?.approval_required,
    );
    const approvalStatus = resolveString(
      rawMetadata?.approval_status,
      transparency?.approval_status,
      rawPayload?.approval_status,
    );
    const approvalReason = resolveString(
      rawMetadata?.approval_reason,
      transparency?.approval_reason,
      rawPayload?.approval_reason,
    );
    const approvalCategories = resolveString(
      rawMetadata?.approval_categories,
      transparency?.approval_categories,
      rawPayload?.approval_categories,
    );
    const approvalRiskLevel = resolveString(
      rawMetadata?.approval_risk_level,
      transparency?.approval_risk_level,
      rawPayload?.approval_risk_level,
    );
    const approvalPolicyVersion = resolveString(
      rawMetadata?.approval_policy_version,
      transparency?.approval_policy_version,
      rawPayload?.approval_policy_version,
    );
    const approvalRequestedAt = resolveString(
      rawMetadata?.approval_requested_at,
      transparency?.approval_requested_at,
      rawPayload?.approval_requested_at,
    );
    const approvalTimeoutSeconds = resolveNumber(
      rawMetadata?.approval_timeout_seconds,
      transparency?.approval_timeout_seconds,
      rawPayload?.approval_timeout_seconds,
    );
    const approvalDecidedAt = resolveString(
      rawMetadata?.approval_decided_at,
      transparency?.approval_decided_at,
      rawPayload?.approval_decided_at,
    );
    const approvalDecidedBy = resolveString(
      rawMetadata?.approval_decided_by,
      transparency?.approval_decided_by,
      rawPayload?.approval_decided_by,
    );
    const approvalDecisionReason = resolveString(
      rawMetadata?.approval_decision_reason,
      transparency?.approval_decision_reason,
      rawPayload?.approval_decision_reason,
    );

    return {
      type: "assistant-complete",
      content,
      checkpoints: buildCheckpoints(intent, route),
      timestamp,
      intent,
      route,
      processingMs,
      analysisQuestion,
      generatedSql,
      validatedSql,
      rowsReturned,
      sqlRetries,
      sqlExecutionMs,
      sqlLastResortFallback,
      sqlLastError,
      schemaSource,
      schemaTablesCount,
      schemaCatalogMissing,
      stageTiming,
      resultPreview,
      subQueryCount,
      subQueriesExecuted,
      subQueriesFailed,
      criticValidated,
      approvalRequired,
      approvalStatus,
      approvalReason,
      approvalCategories,
      approvalRiskLevel,
      approvalPolicyVersion,
      approvalRequestedAt,
      approvalTimeoutSeconds,
      approvalDecidedAt,
      approvalDecidedBy,
      approvalDecisionReason,
    };
  }

  if (eventType === "approval.required") {
    const categories = resolveStringArray(rawPayload?.categories) ?? [];
    const timeoutSeconds =
      resolveNumber(rawPayload?.timeout_seconds, rawPayload?.timeoutSeconds) ??
      180;
    const correlationId =
      typeof event.correlation_id === "string" ? event.correlation_id : "";

    if (!correlationId) {
      return null;
    }

    return {
      type: "approval-required",
      correlationId,
      message:
        resolveString(rawPayload?.message) ??
        "Sensitive query detected. Approval required.",
      reason: resolveString(rawPayload?.reason),
      categories,
      riskLevel: resolveString(rawPayload?.risk_level, rawPayload?.riskLevel),
      timeoutSeconds,
      requestedAt: resolveString(
        rawPayload?.requested_at,
        rawPayload?.requestedAt,
      ),
      expiresAt: resolveString(rawPayload?.expires_at, rawPayload?.expiresAt),
      analysisQuestion: resolveString(
        rawPayload?.analysis_question,
        rawPayload?.analysisQuestion,
      ),
      validatedSql: resolveString(
        rawPayload?.validated_sql,
        rawPayload?.validatedSql,
      ),
      timestamp,
    };
  }

  if (eventType === "approval.finalized") {
    const correlationId =
      typeof event.correlation_id === "string" ? event.correlation_id : "";
    const approved =
      resolveBoolean(rawPayload?.approved) ??
      resolveString(rawPayload?.status) === "approved";
    const statusRaw =
      resolveString(rawPayload?.status)?.toLowerCase() ?? "rejected";
    const status =
      statusRaw === "approved" || statusRaw === "expired"
        ? statusRaw
        : "rejected";

    if (!correlationId) {
      return null;
    }

    return {
      type: "approval-finalized",
      correlationId,
      approved,
      status,
      decidedAt: resolveString(rawPayload?.decided_at, rawPayload?.decidedAt),
      decidedBy: resolveString(rawPayload?.decided_by, rawPayload?.decidedBy),
      reason: resolveString(rawPayload?.reason),
      timestamp,
    };
  }

  if (eventType === "error") {
    const message =
      typeof rawPayload?.message === "string"
        ? rawPayload.message
        : "Error reported by backend";

    return {
      type: "status",
      status: "error",
      message,
      timestamp,
    };
  }

  return null;
};

const parseWebPubSubFrame = (
  event: MessageEvent<string>,
): Record<string, unknown> | null => {
  try {
    const parsed = JSON.parse(event.data) as Record<string, unknown>;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }

    return parsed;
  } catch {
    return null;
  }
};

const formatMessageTime = (timestamp: string): string => {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
};

const buildInitialAssistantContent = (suggestions: string[]): string => {
  if (!suggestions.length) {
    return INITIAL_ASSISTANT_CONTENT;
  }

  const renderedSuggestions = suggestions.map((item) => `- ${item}`).join("\n");
  return `${INITIAL_ASSISTANT_CONTENT}\n\nInitial suggestions:\n${renderedSuggestions}`;
};

const createInitialAssistantMessage = (content: string): ChatMessage => ({
  id: nanoid(),
  role: "assistant",
  content,
  timestamp: new Date().toISOString(),
});

const isValidSessionId = (value: string): boolean =>
  /^[a-zA-Z0-9_-]{6,80}$/.test(value);

const defaultCheckpointsForRoute = (route: PipelineRoute): string[] => {
  if (route === "sql_pipeline") {
    return ["Planner", "Librarian", "SQL Coder", "Critic", "Evaluator"];
  }

  return ["Planner", "Evaluator"];
};

const prettifyStageLabel = (label: string): string => {
  const withoutAgentSuffix = label.replace(/agent$/i, "");
  const withSpaces = withoutAgentSuffix
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ")
    .trim();

  return withSpaces || label;
};

const parseStageTiming = (
  stageTiming?: string,
): Array<{ label: string; ms: number }> => {
  if (!stageTiming) {
    return [];
  }

  return stageTiming
    .split("|")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const [rawLabel, rawMs] = item.split(":");
      const msMatch = rawMs?.match(/\d+/);
      const ms = msMatch ? Number.parseInt(msMatch[0], 10) : Number.NaN;

      return {
        label: prettifyStageLabel(rawLabel?.trim() ?? "Stage"),
        ms,
      };
    })
    .filter((entry) => Number.isFinite(entry.ms));
};

const cleanMessageContent = (content: string) => {
  if (!content) return content;
  const trimmed = content.trim();
  const match = trimmed.match(/^```[a-z]*\s+([\s\S]*?)```$/i);
  return match ? match[1].trim() : content;
};

function HomePageClient() {
  const { data: session } = useSession();
  const [isClientMounted, setIsClientMounted] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [socketStatus, setSocketStatus] =
    useState<SocketStatus>("disconnected");
  const [agentStatus, setAgentStatus] = useState("No activity");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAssistantThinking, setIsAssistantThinking] = useState(false);
  const [pipelineRoute, setPipelineRoute] = useState<PipelineRoute>("general");
  const [pipelineCheckpoints, setPipelineCheckpoints] = useState<string[]>(
    defaultCheckpointsForRoute("general"),
  );
  const [activeStageIndex, setActiveStageIndex] = useState(-1);
  const [pipelineCompleted, setPipelineCompleted] = useState(false);
  const [pipelineError, setPipelineError] = useState(false);
  const [transparencySnapshot, setTransparencySnapshot] =
    useState<TransparencySnapshot | null>(null);
  const [lastSubmittedMessage, setLastSubmittedMessage] = useState("");
  const [pendingApproval, setPendingApproval] =
    useState<PendingApprovalState | null>(null);
  const [isApprovalSubmitting, setIsApprovalSubmitting] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const connectInFlightRef = useRef(false);
  const allowReconnectRef = useRef(true);
  const reconnectTimerRef = useRef<number | null>(null);
  const streamingBufferRef = useRef("");
  const streamingMessageIdRef = useRef<string | null>(null);
  const loadedHistorySessionIdRef = useRef<string | null>(null);
  const stageTickerRef = useRef<number | null>(null);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const clearStageTicker = useCallback(() => {
    if (stageTickerRef.current !== null) {
      window.clearInterval(stageTickerRef.current);
      stageTickerRef.current = null;
    }
  }, []);

  const startStageTicker = useCallback(
    (checkpointCount: number) => {
      clearStageTicker();
      if (checkpointCount <= 1) {
        setActiveStageIndex(0);
        return;
      }

      setActiveStageIndex(0);
      stageTickerRef.current = window.setInterval(() => {
        setActiveStageIndex((prev) => {
          const next = prev + 1;
          return next >= checkpointCount ? checkpointCount - 1 : next;
        });
      }, 900);
    },
    [clearStageTicker],
  );

const handleDownloadPdf = async (elementId: string) => {
    try {
      const element = document.getElementById(elementId);
      if (!element) return;
      
      const printWindow = window.open('', '_blank', `width=${Math.max(800, element.scrollWidth + 100)},height=${element.scrollHeight}`);
      if (!printWindow) {
        toast.error("Could not start printing (pop-up blocker enabled).");
        return;
      }

      const styles = Array.from(document.querySelectorAll('style, link[rel="stylesheet"]'))
        .map(s => s.outerHTML)
        .join('\n');

      const html = `
        <!DOCTYPE html>
        <html>
          <head>
            <title>NIP Report - ${new Date().toLocaleDateString()}</title>
            ${styles}
            <style>
              @page { size: auto; margin: 15mm; }
              body { 
                background: white !important; 
                margin: 0; 
                padding: 20px;
                -webkit-print-color-adjust: exact !important; 
                print-color-adjust: exact !important;
                font-family: system-ui, sans-serif;
              }
              * { color: black !important; border-color: #ddd !important; }
              .glass-subtle, .glass { 
                 background: white !important; box-shadow: none !important; border: none !important;
              }
              .no-print { display: none !important; }
            </style>
          </head>
          <body>
            ${element.outerHTML}
            <script>
              window.onload = () => {
                setTimeout(() => {
                  window.print();
                  window.close();
                }, 500);
              };
            </script>
          </body>
        </html>
      `;

      printWindow.document.open();
      printWindow.document.write(html);
      printWindow.document.close();
      
    } catch (error) {
      console.error('Error generating PDF', error);
      toast.error("Hubo un error al generar el PDF");
    }
  };

  useEffect(() => {
    setIsClientMounted(true);

    const storedSessionId = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (storedSessionId && isValidSessionId(storedSessionId)) {
      setSessionId(storedSessionId);
      return;
    }

    const generatedSessionId = nanoid(14);
    window.localStorage.setItem(SESSION_STORAGE_KEY, generatedSessionId);
    setSessionId(generatedSessionId);
  }, []);

  useEffect(() => {
    if (
      !isClientMounted ||
      !sessionId ||
      loadedHistorySessionIdRef.current === sessionId
    ) {
      return;
    }

    let isCancelled = false;
    loadedHistorySessionIdRef.current = sessionId;

    const loadHistory = async () => {
      try {
        const response = await fetch(
          `/api/realtime/history?sessionId=${encodeURIComponent(sessionId)}&limit=250`,
          {
            method: "GET",
          },
        );

        if (!response.ok) {
          throw new Error("Could not retrieve history");
        }

        const payload = (await response.json()) as {
          messages?: PersistedChatMessageResponse[];
        };

        if (isCancelled) {
          return;
        }

        const restoredMessages = (payload.messages ?? [])
          .filter(
            (message) =>
              message.role === "user" || message.role === "assistant",
          )
          .map((message) => ({
            content: message.content,
            id: message.id,
            role: message.role as ChatRole,
            timestamp: message.timestamp,
          }));

        if (restoredMessages.length > 0) {
          setMessages(restoredMessages);
          return;
        }

        const suggestionsResponse = await fetch(
          "/api/realtime/suggestions?limit=6",
          {
            method: "GET",
          },
        );
        const suggestionsPayload = suggestionsResponse.ok
          ? ((await suggestionsResponse.json()) as StartupSuggestionsResponse)
          : null;
        const suggestions = suggestionsPayload?.suggestions ?? [];
        const welcomeMessage = createInitialAssistantMessage(
          buildInitialAssistantContent(suggestions),
        );
        setMessages([welcomeMessage]);

        await fetch("/api/realtime/history", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            content: welcomeMessage.content,
            id: welcomeMessage.id,
            role: "assistant",
            sessionId,
            source: "next.bootstrap",
            timestamp: welcomeMessage.timestamp,
          }),
        });
      } catch {
        if (isCancelled) {
          return;
        }

        setMessages([createInitialAssistantMessage(INITIAL_ASSISTANT_CONTENT)]);
      }
    };

    void loadHistory();

    return () => {
      isCancelled = true;
    };
  }, [isClientMounted, sessionId]);

  const persistAssistantMessage = useCallback(
    async (content: string, timestamp: string) => {
      if (!sessionId || !content.trim()) {
        return;
      }

      await fetch("/api/realtime/history", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          content,
          role: "assistant",
          sessionId,
          source: "next.realtime-stream",
          timestamp,
        }),
      });
    },
    [sessionId],
  );

  const connectionBadge = useMemo(() => {
    if (socketStatus === "connected") {
      return (
        <Badge className="gap-2" variant="default">
          <WifiIcon className="size-3.5" />
          Connected
        </Badge>
      );
    }

    if (socketStatus === "connecting") {
      return (
        <Badge className="gap-2" variant="secondary">
          <SparklesIcon className="size-3.5 animate-pulse" />
          Connecting
        </Badge>
      );
    }

    return (
      <Badge className="gap-2" variant="destructive">
        <WifiOffIcon className="size-3.5" />
        Disconnected
      </Badge>
    );
  }, [socketStatus]);

  const chatStatus = useMemo<
    "ready" | "submitted" | "streaming" | "error"
  >(() => {
    if (socketStatus === "disconnected") {
      return "error";
    }

    return isSubmitting ? "streaming" : "ready";
  }, [isSubmitting, socketStatus]);

  const routeLabel = useMemo(() => {
    if (pipelineRoute === "sql_pipeline") {
      return "Nexus Insight";
    }
    if (pipelineRoute === "chat_pipeline") {
      return "Chat";
    }
    return "General";
  }, [pipelineRoute]);

  const stageVisualStates = useMemo<PipelineStageState[]>(() => {
    return pipelineCheckpoints.map((_, index) => {
      if (pipelineError) {
        if (index < Math.max(activeStageIndex, 0)) {
          return "completed";
        }
        return index === Math.max(activeStageIndex, 0) ? "error" : "idle";
      }

      if (pipelineCompleted) {
        return "completed";
      }

      if (isSubmitting) {
        if (index < activeStageIndex) {
          return "completed";
        }
        if (index === activeStageIndex) {
          return "running";
        }
      }

      return "idle";
    });
  }, [
    activeStageIndex,
    isSubmitting,
    pipelineCheckpoints,
    pipelineCompleted,
    pipelineError,
  ]);

  const activeStageLabel = useMemo(() => {
    if (activeStageIndex < 0 || pipelineCheckpoints.length === 0) {
      return "Idle";
    }

    const boundedIndex = Math.min(
      activeStageIndex,
      pipelineCheckpoints.length - 1,
    );
    return pipelineCheckpoints[boundedIndex] ?? "Idle";
  }, [activeStageIndex, pipelineCheckpoints]);

  const stageTimeline = useMemo(
    () => parseStageTiming(transparencySnapshot?.stageTiming),
    [transparencySnapshot?.stageTiming],
  );

  const questionDisplayText = useMemo(() => {
    return (
      transparencySnapshot?.analysisQuestion ??
      (lastSubmittedMessage || "No question registered")
    );
  }, [lastSubmittedMessage, transparencySnapshot?.analysisQuestion]);

  const sqlDisplayText = useMemo(() => {
    const sql =
      transparencySnapshot?.validatedSql ?? transparencySnapshot?.generatedSql;
    if (sql) {
      return sql;
    }

    return pipelineRoute === "chat_pipeline"
      ? "Not applicable in Chat route"
      : "No SQL available";
  }, [
    pipelineRoute,
    transparencySnapshot?.generatedSql,
    transparencySnapshot?.validatedSql,
  ]);

  const previewDisplayText = useMemo(() => {
    return transparencySnapshot?.resultPreview ?? "No preview available";
  }, [transparencySnapshot?.resultPreview]);

  const resetStreamingState = useCallback(() => {
    streamingBufferRef.current = "";
    streamingMessageIdRef.current = null;
  }, []);

  const startOrUpdateStreamingMessage = useCallback((token: string) => {
    if (!streamingMessageIdRef.current) {
      const messageId = nanoid();
      streamingMessageIdRef.current = messageId;
      streamingBufferRef.current = "";

      setMessages((prev) => [
        ...prev,
        {
          id: messageId,
          role: "assistant",
          content: "",
          timestamp: new Date().toISOString(),
        },
      ]);
    }

    streamingBufferRef.current += token;

    setMessages((prev) =>
      prev.map((message) => {
        if (message.id !== streamingMessageIdRef.current) {
          return message;
        }

        return {
          ...message,
          content: streamingBufferRef.current,
        };
      }),
    );
  }, []);

  const completeAssistantMessage = useCallback(
    (
      content: string,
      checkpoints: string[],
      timestamp?: string,
      route?: string,
      processingMs?: number,
    ) => {
      const normalizedContent = content.trim();
      const finalTimestamp = timestamp ?? new Date().toISOString();

      if (streamingMessageIdRef.current && normalizedContent) {
        setMessages((prev) =>
          prev.map((message) => {
            if (message.id !== streamingMessageIdRef.current) {
              return message;
            }

            return {
              ...message,
              content: normalizedContent,
            };
          }),
        );
      }

      if (!streamingMessageIdRef.current && normalizedContent) {
        setMessages((prev) => [
          ...prev,
          {
            id: nanoid(),
            role: "assistant",
            content: normalizedContent,
            timestamp: finalTimestamp,
          },
        ]);
      }

      if (normalizedContent) {
        void persistAssistantMessage(normalizedContent, finalTimestamp);
      }

      clearStageTicker();
      setPipelineRoute(
        route === "sql_pipeline" || route === "chat_pipeline"
          ? route
          : "general",
      );
      setPipelineCheckpoints(checkpoints);
      setActiveStageIndex(Math.max(0, checkpoints.length - 1));
      setPipelineCompleted(true);
      setPipelineError(false);

      resetStreamingState();
      const routeLabel =
        route === "sql_pipeline"
          ? "Nexus Insight"
          : route === "chat_pipeline"
            ? "Chat"
            : "General";
      const latencyLabel =
        typeof processingMs === "number" ? ` · ${processingMs}ms` : "";
      setAgentStatus(
        `${routeLabel} flow completed${latencyLabel}: ${checkpoints.join(" · ")}`,
      );
      setIsSubmitting(false);
      setIsAssistantThinking(false);
      setPendingApproval(null);
      setIsApprovalSubmitting(false);
    },
    [clearStageTicker, persistAssistantMessage, resetStreamingState],
  );

  const connectRealtime = useCallback(async () => {
    if (!sessionId) {
      return;
    }

    if (connectInFlightRef.current) {
      return;
    }

    allowReconnectRef.current = true;
    connectInFlightRef.current = true;
    clearReconnectTimer();

    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    try {
      setSocketStatus("connecting");

      const negotiateResponse = await fetch("/api/realtime/negotiate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          sessionId,
        }),
      });

      if (!negotiateResponse.ok) {
        throw new Error("Could not negotiate realtime connection.");
      }

      const payload =
        (await negotiateResponse.json()) as RealtimeNegotiateResponse;

      const ws = new WebSocket(payload.url, "json.webpubsub.azure.v1");
      socketRef.current = ws;
      const joinAckId = 1;

      ws.onopen = () => {
        if (socketRef.current !== ws) {
          return;
        }

        ws.send(
          JSON.stringify({
            type: "joinGroup",
            group: payload.group,
            ackId: joinAckId,
          }),
        );

        setAgentStatus("Connecting to realtime group...");
      };

      ws.onmessage = (event) => {
        if (socketRef.current !== ws) {
          return;
        }

        const frame = parseWebPubSubFrame(event);
        if (!frame) {
          return;
        }

        const frameType =
          typeof frame.type === "string" ? frame.type : undefined;

        if (frameType === "ack") {
          const ackId =
            typeof frame.ackId === "number" ? frame.ackId : undefined;

          if (ackId !== joinAckId) {
            return;
          }

          const success = frame.success === true;
          if (success) {
            setSocketStatus("connected");
            setAgentStatus("Connected to Azure Web PubSub");
            return;
          }

          const error =
            frame.error && typeof frame.error === "object"
              ? frame.error
              : undefined;
          const name =
            error && "name" in error && typeof error.name === "string"
              ? error.name
              : "JoinGroupFailed";
          const message =
            error && "message" in error && typeof error.message === "string"
              ? error.message
              : "No details";

          setSocketStatus("disconnected");
          setAgentStatus(`${name}: ${message}`);
          setIsSubmitting(false);
          setIsAssistantThinking(false);
          ws.close();
          return;
        }

        const rawEvent = parseWebPubSubPayload(event);
        if (!rawEvent) {
          return;
        }

        const serverEvent = normalizeRealtimeEvent(rawEvent);
        if (!serverEvent) {
          return;
        }

        if (serverEvent.type === "status") {
          setAgentStatus(normalizeStatusLabel(serverEvent));
          if (serverEvent.status === "processing") {
            const checkpoints = defaultCheckpointsForRoute(pipelineRoute);
            setPipelineCheckpoints(checkpoints);
            setPipelineCompleted(false);
            setPipelineError(false);
            startStageTicker(checkpoints.length);
          }

          if (serverEvent.status === "completed") {
            clearStageTicker();
          }

          if (serverEvent.status === "error") {
            setIsSubmitting(false);
            setIsAssistantThinking(false);
            clearStageTicker();
            setPipelineCompleted(false);
            setPipelineError(true);
            resetStreamingState();
          }
          return;
        }

        if (serverEvent.type === "assistant-token") {
          setIsAssistantThinking(false);
          if (serverEvent.token) {
            startOrUpdateStreamingMessage(serverEvent.token);
          }

          return;
        }

        if (serverEvent.type === "assistant-complete") {
          setTransparencySnapshot({
            analysisQuestion:
              serverEvent.analysisQuestion ?? lastSubmittedMessage,
            generatedSql: serverEvent.generatedSql,
            validatedSql: serverEvent.validatedSql,
            rowsReturned: serverEvent.rowsReturned,
            sqlRetries: serverEvent.sqlRetries,
            sqlExecutionMs: serverEvent.sqlExecutionMs,
            sqlLastResortFallback: serverEvent.sqlLastResortFallback,
            sqlLastError: serverEvent.sqlLastError,
            schemaSource: serverEvent.schemaSource,
            schemaTablesCount: serverEvent.schemaTablesCount,
            schemaCatalogMissing: serverEvent.schemaCatalogMissing,
            stageTiming: serverEvent.stageTiming,
            resultPreview: serverEvent.resultPreview,
            subQueryCount: serverEvent.subQueryCount,
            subQueriesExecuted: serverEvent.subQueriesExecuted,
            subQueriesFailed: serverEvent.subQueriesFailed,
            criticValidated: serverEvent.criticValidated,
            approvalRequired: serverEvent.approvalRequired,
            approvalStatus: serverEvent.approvalStatus,
            approvalReason: serverEvent.approvalReason,
            approvalCategories: serverEvent.approvalCategories,
            approvalRiskLevel: serverEvent.approvalRiskLevel,
            approvalPolicyVersion: serverEvent.approvalPolicyVersion,
            approvalRequestedAt: serverEvent.approvalRequestedAt,
            approvalTimeoutSeconds: serverEvent.approvalTimeoutSeconds,
            approvalDecidedAt: serverEvent.approvalDecidedAt,
            approvalDecidedBy: serverEvent.approvalDecidedBy,
            approvalDecisionReason: serverEvent.approvalDecisionReason,
          });
          completeAssistantMessage(
            serverEvent.content,
            serverEvent.checkpoints,
            serverEvent.timestamp,
            serverEvent.route,
            serverEvent.processingMs,
          );
          return;
        }

        if (serverEvent.type === "approval-required") {
          clearStageTicker();
          setIsSubmitting(true);
          setIsAssistantThinking(false);
          setPipelineRoute("sql_pipeline");
          setPipelineCheckpoints(defaultCheckpointsForRoute("sql_pipeline"));
          setActiveStageIndex(3);
          setPipelineCompleted(false);
          setPipelineError(false);
          setPendingApproval({
            correlationId: serverEvent.correlationId,
            message: serverEvent.message,
            reason: serverEvent.reason,
            categories: serverEvent.categories ?? [],
            riskLevel: serverEvent.riskLevel,
            timeoutSeconds: serverEvent.timeoutSeconds,
            requestedAt: serverEvent.requestedAt,
            expiresAt: serverEvent.expiresAt,
            analysisQuestion: serverEvent.analysisQuestion,
            validatedSql: serverEvent.validatedSql,
          });
          setAgentStatus("Waiting for human approval for sensitive query");
          setTransparencySnapshot((previous) => ({
            ...(previous ?? {}),
            analysisQuestion:
              serverEvent.analysisQuestion ?? previous?.analysisQuestion,
            validatedSql: serverEvent.validatedSql ?? previous?.validatedSql,
            approvalRequired: true,
            approvalStatus: "pending",
            approvalReason: serverEvent.reason,
            approvalCategories: (serverEvent.categories ?? []).join(","),
            approvalRiskLevel: serverEvent.riskLevel,
            approvalRequestedAt: serverEvent.requestedAt,
            approvalTimeoutSeconds: serverEvent.timeoutSeconds,
          }));
          return;
        }

        if (serverEvent.type === "approval-finalized") {
          setTransparencySnapshot((previous) => ({
            ...(previous ?? {}),
            approvalStatus: serverEvent.status,
            approvalDecidedAt: serverEvent.decidedAt,
            approvalDecidedBy: serverEvent.decidedBy,
            approvalDecisionReason: serverEvent.reason,
          }));

          if (!serverEvent.approved) {
            setPendingApproval(null);
            setIsSubmitting(true);
            setIsAssistantThinking(false);
            setAgentStatus(
              serverEvent.status === "expired"
                ? "Approval expired. Query cancelled by compliance."
                : "Sensitive query rejected.",
            );
          }
        }
      };

      ws.onclose = (event) => {
        if (socketRef.current !== ws) {
          return;
        }

        socketRef.current = null;
        setSocketStatus("disconnected");
        setIsAssistantThinking(false);

        const closeDetail = formatCloseDetail(event);
        setAgentStatus(`Connection closed (${closeDetail})`);

        if (!allowReconnectRef.current) {
          return;
        }

        reconnectTimerRef.current = window.setTimeout(() => {
          connectRealtime().catch(() => {
            setSocketStatus("disconnected");
            setAgentStatus("Could not reconnect with Azure Web PubSub");
          });
        }, SOCKET_RETRY_MS);
      };

      ws.onerror = () => {
        if (socketRef.current !== ws) {
          return;
        }

        setSocketStatus("disconnected");
        setAgentStatus("WebSocket connection error");
        setIsSubmitting(false);
        setIsAssistantThinking(false);
        resetStreamingState();
      };
    } finally {
      connectInFlightRef.current = false;
    }
  }, [
    clearReconnectTimer,
    clearStageTicker,
    completeAssistantMessage,
    lastSubmittedMessage,
    pipelineRoute,
    resetStreamingState,
    sessionId,
    startStageTicker,
    startOrUpdateStreamingMessage,
  ]);

  const submitApprovalDecision = useCallback(
    async (approved: boolean) => {
      if (!pendingApproval || !sessionId || isApprovalSubmitting) {
        return;
      }

      setIsApprovalSubmitting(true);
      try {
        const response = await fetch("/api/realtime/approval", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            sessionId,
            correlationId: pendingApproval.correlationId,
            approved,
            reason: approved ? "Aprobado por usuario" : "Rechazado por usuario",
          }),
        });

        if (!response.ok) {
          throw new Error("Could not send approval decision");
        }

        setAgentStatus(
          approved
            ? "Approval sent. Resuming execution..."
            : "Rejection sent. Cancelling execution...",
        );
      } catch {
        toast.error("Could not send approval decision");
      } finally {
        setIsApprovalSubmitting(false);
      }
    },
    [isApprovalSubmitting, pendingApproval, sessionId],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      connectRealtime().catch(() => {
        setSocketStatus("disconnected");
        setAgentStatus("Could not connect with Azure Web PubSub");
        toast.error("Realtime connection error", {
          description:
            "Verify AZURE_WEBPUBSUB_CONNECTION_STRING, AZURE_WEBPUBSUB_HUB_NAME and AZURE_WEBPUBSUB_GROUP on the backend.",
        });
      });
    }, 0);

    return () => {
      allowReconnectRef.current = false;
      window.clearTimeout(timer);
      clearReconnectTimer();
      clearStageTicker();
      socketRef.current?.close();
      socketRef.current = null;
      setIsAssistantThinking(false);
      resetStreamingState();
    };
  }, [
    clearReconnectTimer,
    clearStageTicker,
    connectRealtime,
    resetStreamingState,
  ]);

  const sendMessage = useCallback(
    async (rawText: string) => {
      const text = rawText.trim();
      if (!text || isSubmitting) {
        return;
      }

      if (!sessionId) {
        toast.error("Realtime session not initialized");
        return;
      }

      if (socketStatus !== "connected") {
        toast.error("No realtime connection", {
          description: "Reconnect before sending messages.",
        });
        return;
      }

      setIsSubmitting(true);
      setIsAssistantThinking(true);
      setPipelineCompleted(false);
      setPipelineError(false);
      setPipelineRoute("general");
      setPipelineCheckpoints(defaultCheckpointsForRoute("general"));
      setActiveStageIndex(0);
      setTransparencySnapshot(null);
      setLastSubmittedMessage(text);
      setPendingApproval(null);
      setIsApprovalSubmitting(false);
      setInput("");

      const userMessage: ChatMessage = {
        id: nanoid(),
        role: "user",
        content: text,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);

      try {
        const response = await fetch("/api/realtime/message", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            sessionId,
            text,
            model: FIXED_MODEL.id,
          }),
        });

        if (!response.ok) {
          setIsSubmitting(false);
          setIsAssistantThinking(false);
          resetStreamingState();
          toast.error("Could not process message", {
            description: "Agent backend returned an error.",
          });
        }
      } catch {
        setIsSubmitting(false);
        setIsAssistantThinking(false);
        resetStreamingState();
        toast.error("Could not send message", {
          description: "Check connection with realtime backend.",
        });
      }
    },
    [isSubmitting, resetStreamingState, sessionId, socketStatus],
  );

  const handlePromptSubmit = useCallback(
    async (message: PromptInputMessage) => {
      if (message.files.length > 0) {
        toast.error("Attachments not supported", {
          description: "Currently only text messages are allowed.",
        });
        return;
      }

      await sendMessage(message.text);
    },
    [sendMessage],
  );

  const handleReconnect = useCallback(() => {
    connectRealtime().catch(() => {
      setSocketStatus("disconnected");
      setAgentStatus("Could not reconnect with Azure Web PubSub");
      toast.error("Reconnection failed");
    });
  }, [connectRealtime]);

  const handleResetChat = useCallback(async () => {
    if (!sessionId) {
      return;
    }

    const previousSessionId = sessionId;

    setInput("");
    setIsSubmitting(false);
    setIsAssistantThinking(false);
    clearStageTicker();
    setPipelineRoute("general");
    setPipelineCheckpoints(defaultCheckpointsForRoute("general"));
    setActiveStageIndex(-1);
    setPipelineCompleted(false);
    setPipelineError(false);
    setTransparencySnapshot(null);
    setLastSubmittedMessage("");
    setPendingApproval(null);
    setIsApprovalSubmitting(false);
    resetStreamingState();
    setAgentStatus("Resetting session...");
    setMessages([]);

    try {
      const response = await fetch(
        `/api/realtime/history?sessionId=${encodeURIComponent(previousSessionId)}`,
        {
          method: "DELETE",
        },
      );

      if (!response.ok) {
        throw new Error("Could not clear history");
      }
    } catch {
      toast.error("Could not clear previous history");
    }

    const nextSessionId = nanoid(14);
    window.localStorage.setItem(SESSION_STORAGE_KEY, nextSessionId);
    loadedHistorySessionIdRef.current = null;
    setSessionId(nextSessionId);
    setAgentStatus("Session reset");
    toast.success("Chat reset");
  }, [clearStageTicker, resetStreamingState, sessionId]);

  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInput(event.target.value);
    },
    [],
  );

  return (
    <main className="flex min-h-screen w-full items-center justify-center bg-gradient-to-br from-[oklch(0.08_0.02_260)] via-background to-[oklch(0.1_0.015_280)] px-3 py-4">
      {/* Ambient glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 size-96 rounded-full bg-[oklch(0.72_0.19_250/6%)] blur-3xl" />
        <div className="absolute -bottom-40 -right-40 size-96 rounded-full bg-[oklch(0.68_0.18_290/5%)] blur-3xl" />
      </div>

      <Card className="relative flex h-[96vh] w-full max-w-7xl flex-col overflow-hidden border-white/8 bg-card/90 shadow-2xl shadow-black/30 backdrop-blur-sm">
        {/* ─── Header ─── */}
        <div className="glass border-b border-white/8 px-5 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="relative flex size-9 items-center justify-center rounded-xl shadow-lg">
                <NexusLogo className="size-9" />
                {isSubmitting && (
                  <div className="absolute -inset-0.5 animate-pipeline-glow rounded-xl" />
                )}
              </div>
              <div>
                <h1 className="text-base font-bold tracking-tight text-foreground">
                  Nexus Insight
                </h1>
                <p className="text-[11px] text-muted-foreground">
                  Query-to-Insight Analytics Engine
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {connectionBadge}
              {isSubmitting && (
                <Badge
                  variant="secondary"
                  className="gap-1.5 text-[10px] border-white/10 bg-white/6"
                >
                  <SparklesIcon className="size-3 animate-pulse text-blue-400" />
                  {isAssistantThinking ? "Thinking" : "Generating"}
                </Badge>
              )}
              <Badge
                variant="outline"
                className="max-w-[22rem] truncate text-[10px] border-white/10 bg-white/3"
              >
                {agentStatus}
              </Badge>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 text-xs border-white/10 bg-white/3 hover:bg-white/8 transition-colors"
                onClick={handleReconnect}
                disabled={socketStatus === "connecting"}
              >
                <RefreshCwIcon className="size-3" />
                Reconnect
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="text-xs border-white/10 bg-white/3 hover:bg-white/8 transition-colors"
                onClick={handleResetChat}
                disabled={isSubmitting}
              >
                New chat
              </Button>
              <LogoutButton />
            </div>
          </div>

          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-white/5 pt-2">
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <Badge
                variant="secondary"
                className="gap-1.5 text-[10px] bg-white/5 border-white/8"
              >
                <ModelSelectorLogo provider={FIXED_MODEL.chefSlug} />
                <span>{FIXED_MODEL.name}</span>
              </Badge>
              <Badge variant="outline" className="text-[10px] border-white/8">
                {routeLabel}
              </Badge>
            </div>
            <p className="flex items-center gap-2 text-[10px] text-muted-foreground/60">
              {session?.user?.name && (
                <span className="font-semibold text-foreground/70">
                  {session.user.name}
                </span>
              )}
              <span className="font-mono text-foreground/50">
                {sessionId || "..."}
              </span>
            </p>
          </div>
        </div>

        {/* ─── Main Grid ─── */}
        <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1.4fr)_minmax(340px,0.6fr)]">
          {/* ─── Chat Panel ─── */}
          <div className="flex min-h-0 flex-col border-white/5 lg:border-r">
            {isClientMounted ? (
              <Conversation className="min-h-0 flex-1 bg-muted/15">
                <ConversationContent className="mx-auto w-full max-w-none gap-5 px-6 py-6">
                  {messages.map((message) => (
                    <Message from={message.role} key={message.id}>
                      {message.role === "assistant" ? (
                        <div className="glass-subtle rounded-xl px-4 py-3">
                          <div className="mb-2 flex items-center justify-between gap-3">
                            <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-neon">
                              Agent
                            </p>
                            <span className="text-[10px] text-muted-foreground/60">
                              {formatMessageTime(message.timestamp)}
                            </span>
                          </div>
                          <MessageContent id={`message-${message.id}`} className="text-[14px] leading-6 text-foreground/90">
                            <MessageResponse>{cleanMessageContent(message.content)}</MessageResponse>
                          </MessageContent>
                          
                          {cleanMessageContent(message.content).length > 200 && (
                            /^#{1,4}\s/m.test(cleanMessageContent(message.content)) || /\|.*\|.*\|/m.test(cleanMessageContent(message.content))
                          ) && (
                            <div className="mt-3 flex justify-end border-t border-white/5 pt-2 no-print">
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                onClick={() => handleDownloadPdf(`message-${message.id}`)}
                                className="h-7 text-xs text-muted-foreground hover:text-foreground no-print"
                              >
                                <PrinterIcon className="mr-2 size-3" />
                                Print PDF Report
                              </Button>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="ml-auto w-fit max-w-full space-y-1">
                          <div className="flex items-center justify-end gap-2 px-1">
                            <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
                              You
                            </p>
                            <span className="text-[10px] text-muted-foreground/60">
                              {formatMessageTime(message.timestamp)}
                            </span>
                          </div>
                          <div className="rounded-xl border border-blue-500/15 bg-blue-500/5 px-4 py-3">
                            <MessageContent className="text-[14px] leading-6">
                              <MessageResponse>
                                {message.content}
                              </MessageResponse>
                            </MessageContent>
                          </div>
                        </div>
                      )}
                    </Message>
                  ))}

                  {isAssistantThinking && (
                    <Message
                      from="assistant"
                      key="assistant-thinking-indicator"
                    >
                      <div className="glass-subtle rounded-xl px-4 py-3">
                        <div className="mb-2 flex items-center justify-between gap-3">
                          <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-neon">
                            Agent
                          </p>
                          <span className="text-[10px] text-muted-foreground/60">
                            Generating...
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <SparklesIcon className="size-4 animate-pulse text-blue-400" />
                          <span>Thinking the best response</span>
                          <div className="ml-1 flex items-center gap-1">
                            <span className="size-1.5 animate-pulse rounded-full bg-blue-400 [animation-delay:0ms]" />
                            <span className="size-1.5 animate-pulse rounded-full bg-purple-400 [animation-delay:200ms]" />
                            <span className="size-1.5 animate-pulse rounded-full bg-cyan-400 [animation-delay:400ms]" />
                          </div>
                        </div>
                      </div>
                    </Message>
                  )}
                </ConversationContent>
                <ConversationScrollButton />
              </Conversation>
            ) : (
              <div className="flex-1 bg-muted/15">
                <div className="mx-auto flex h-full w-full max-w-none flex-col gap-5 px-6 py-6">
                  <div className="w-full max-w-[82%] rounded-xl border border-border/70 bg-background/80 px-4 py-3">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div className="h-3 w-14 animate-pulse rounded bg-muted" />
                      <div className="h-3 w-16 animate-pulse rounded bg-muted" />
                    </div>
                    <div className="space-y-2">
                      <div className="h-3 w-full animate-pulse rounded bg-muted" />
                      <div className="h-3 w-[92%] animate-pulse rounded bg-muted" />
                      <div className="h-3 w-[68%] animate-pulse rounded bg-muted" />
                    </div>
                  </div>

                  <div className="ml-auto w-full max-w-[70%] rounded-xl border border-primary/30 bg-primary/10 px-4 py-3">
                    <div className="mb-3 flex items-center justify-end gap-3">
                      <div className="h-3 w-8 animate-pulse rounded bg-muted" />
                      <div className="h-3 w-14 animate-pulse rounded bg-muted" />
                    </div>
                    <div className="space-y-2">
                      <div className="ml-auto h-3 w-full animate-pulse rounded bg-muted" />
                      <div className="ml-auto h-3 w-[78%] animate-pulse rounded bg-muted" />
                    </div>
                  </div>

                  <div className="w-full max-w-[88%] rounded-xl border border-border/70 bg-background/80 px-4 py-3">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div className="h-3 w-14 animate-pulse rounded bg-muted" />
                      <div className="h-3 w-16 animate-pulse rounded bg-muted" />
                    </div>
                    <div className="space-y-2">
                      <div className="h-3 w-full animate-pulse rounded bg-muted" />
                      <div className="h-3 w-[89%] animate-pulse rounded bg-muted" />
                      <div className="h-3 w-[74%] animate-pulse rounded bg-muted" />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {isSubmitting && (
              <div className="border-t border-border/70 bg-card/70 px-6 py-2">
                <div className="mx-auto w-full max-w-none">
                  <div className="mb-1.5 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-xs font-medium text-foreground/80">
                      <SparklesIcon className="size-3.5 animate-pulse text-blue-400" />
                      <span>
                        {isAssistantThinking
                          ? "The agent is thinking the best strategy..."
                          : "The agent is generating the response..."}
                      </span>
                    </div>
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      {isAssistantThinking ? "Thinking" : "Streaming"}
                    </span>
                  </div>

                  <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted/40">
                    <div className="absolute inset-y-0 left-0 h-full w-2/5 rounded-full bg-gradient-to-r from-blue-500 via-purple-500 to-cyan-400 animate-pipeline-flow" />
                    <div className="absolute inset-0 animate-shimmer" />
                  </div>
                </div>
              </div>
            )}

            <div className="border-t border-border bg-card px-6 pt-4 pb-5">
              <div className="mx-auto grid w-full max-w-none gap-3">
                <PromptInput
                  maxFiles={0}
                  onError={({ code }) => {
                    if (code === "max_files") {
                      toast.error("Attachments not supported", {
                        description:
                          "Currently only text messages are allowed.",
                      });
                    }
                  }}
                  onSubmit={handlePromptSubmit}
                >
                  <PromptInputBody>
                    <PromptInputTextarea
                      onChange={handleInputChange}
                      value={input}
                      placeholder="Describe your request: security, performance, architecture or UX..."
                      className="min-h-20 opacity-100 disabled:opacity-25 disabled:cursor-not-allowed"
                    />
                  </PromptInputBody>

                  <PromptInputFooter>
                    <PromptInputTools>
                      <PromptInputButton disabled variant="secondary">
                        <ModelSelectorLogo provider={FIXED_MODEL.chefSlug} />
                        <ModelSelectorName>
                          {FIXED_MODEL.name}
                        </ModelSelectorName>
                      </PromptInputButton>
                    </PromptInputTools>

                    <div className="flex items-center gap-3">
                      <p className="hidden text-xs text-muted-foreground md:block">
                        Enter to send · Shift+Enter for new line
                      </p>
                      <PromptInputSubmit
                        disabled={!input.trim() || isSubmitting}
                        status={chatStatus}
                      />
                    </div>
                  </PromptInputFooter>
                </PromptInput>
              </div>
            </div>
          </div>

          {/* ─── Sidebar: Pipeline Panel ─── */}
          <aside className="min-h-0 space-y-3 overflow-y-auto px-3 py-3">
            <PipelineVisualization
              checkpoints={pipelineCheckpoints}
              stageStates={stageVisualStates}
              isProcessing={isSubmitting}
              isCompleted={pipelineCompleted}
              isError={pipelineError}
              activeIndex={activeStageIndex}
              route={pipelineRoute}
            />

            {pendingApproval && (
              <Card className="space-y-3 border-orange-500/50 bg-orange-500/20 p-3">
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-orange-600">
                    Human Approval Required
                  </p>
                  <p className="text-sm text-foreground/90">
                    {pendingApproval.message}
                  </p>
                </div>

                <div className="space-y-1 text-xs text-muted-foreground">
                  {pendingApproval.riskLevel && (
                    <p>Risk: {pendingApproval.riskLevel}</p>
                  )}
                  {pendingApproval.categories.length > 0 && (
                    <p>Categories: {pendingApproval.categories.join(", ")}</p>
                  )}
                  {pendingApproval.reason && (
                    <p>Reason: {pendingApproval.reason}</p>
                  )}
                  <p>Timeout: {pendingApproval.timeoutSeconds}s</p>
                </div>

                <div className="max-h-32 overflow-auto rounded-md border border-border/60 bg-background/70 p-2">
                  <p className="font-mono text-[11px] whitespace-pre-wrap text-foreground/80">
                    {pendingApproval.validatedSql ??
                      "No validated SQL available"}
                  </p>
                </div>

                <div className="flex items-center justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      void submitApprovalDecision(false);
                    }}
                    disabled={isApprovalSubmitting}
                  >
                    Reject
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => {
                      void submitApprovalDecision(true);
                    }}
                    disabled={isApprovalSubmitting}
                  >
                    Approve
                  </Button>
                </div>
              </Card>
            )}

            <ExecutionTimeline
              stages={stageTimeline}
              totalMs={
                typeof transparencySnapshot?.sqlExecutionMs === "number"
                  ? transparencySnapshot.sqlExecutionMs
                  : undefined
              }
            />

            <TransparencyPanel
              question={questionDisplayText}
              sql={sqlDisplayText}
              preview={previewDisplayText}
              rowsReturned={transparencySnapshot?.rowsReturned}
              sqlRetries={transparencySnapshot?.sqlRetries}
              schemaSource={transparencySnapshot?.schemaSource}
              schemaTablesCount={transparencySnapshot?.schemaTablesCount}
              fallback={transparencySnapshot?.sqlLastResortFallback}
              lastError={transparencySnapshot?.sqlLastError}
              subQueryCount={transparencySnapshot?.subQueryCount}
              subQueriesExecuted={transparencySnapshot?.subQueriesExecuted}
              subQueriesFailed={transparencySnapshot?.subQueriesFailed}
              criticValidated={transparencySnapshot?.criticValidated}
              sqlExecutionMs={transparencySnapshot?.sqlExecutionMs}
              route={pipelineRoute}
            />
          </aside>
        </div>
      </Card>
    </main>
  );
}

export default dynamic(() => Promise.resolve(HomePageClient), {
  ssr: false,
});
