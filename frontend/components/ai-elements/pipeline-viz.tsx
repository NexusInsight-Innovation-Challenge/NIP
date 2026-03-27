"use client";

import { useMemo } from "react";
import {
  BrainCircuitIcon,
  BookOpenIcon,
  CodeIcon,
  ShieldCheckIcon,
  PlayIcon,
  SparklesIcon,
  CheckCircle2Icon,
  XCircleIcon,
  LoaderIcon,
  ChevronRightIcon,
  DatabaseIcon,
  CpuIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

type StageState = "idle" | "running" | "completed" | "error";

interface StageConfig {
  label: string;
  icon: React.ReactNode;
  color: string;
  glowColor: string;
  description: string;
}

const PIPELINE_STAGES: Record<string, StageConfig> = {
  Planner: {
    label: "Planner",
    icon: <BrainCircuitIcon className="size-4" />,
    color: "from-violet-500 to-purple-600",
    glowColor: "oklch(0.68 0.18 290)",
    description: "Descompone la pregunta",
  },
  Librarian: {
    label: "Librarian",
    icon: <BookOpenIcon className="size-4" />,
    color: "from-cyan-500 to-blue-500",
    glowColor: "oklch(0.78 0.15 200)",
    description: "Schema & FK context",
  },
  "SQL Coder": {
    label: "SQL Coder",
    icon: <CodeIcon className="size-4" />,
    color: "from-blue-500 to-indigo-600",
    glowColor: "oklch(0.72 0.19 250)",
    description: "Genera SQL experto",
  },
  Critic: {
    label: "Critic",
    icon: <ShieldCheckIcon className="size-4" />,
    color: "from-amber-500 to-orange-500",
    glowColor: "oklch(0.82 0.15 80)",
    description: "Valida seguridad",
  },
  Execution: {
    label: "Execution",
    icon: <PlayIcon className="size-4" />,
    color: "from-emerald-500 to-green-500",
    glowColor: "oklch(0.75 0.17 160)",
    description: "Ejecuta queries",
  },
  Evaluator: {
    label: "Evaluator",
    icon: <SparklesIcon className="size-4" />,
    color: "from-pink-500 to-rose-500",
    glowColor: "oklch(0.65 0.2 340)",
    description: "Reporte ejecutivo",
  },
};

const DEFAULT_CONFIG: StageConfig = {
  label: "Stage",
  icon: <CpuIcon className="size-4" />,
  color: "from-gray-500 to-gray-600",
  glowColor: "oklch(0.5 0 0)",
  description: "",
};

interface PipelineVisualizationProps {
  checkpoints: string[];
  stageStates: StageState[];
  isProcessing: boolean;
  isCompleted: boolean;
  isError: boolean;
  activeIndex: number;
  route: string;
}

function StageNode({
  config,
  state,
  index,
  isLast,
}: {
  config: StageConfig;
  state: StageState;
  index: number;
  isLast: boolean;
}) {
  const stateStyles = useMemo(() => {
    switch (state) {
      case "running":
        return "stage-glow-running border-blue-500/40 bg-gradient-to-br from-blue-50 to-blue-100/50 shadow-md";
      case "completed":
        return "stage-glow-completed border-emerald-500/40 bg-gradient-to-br from-emerald-50 to-emerald-100/50 shadow-md";
      case "error":
        return "stage-glow-error border-red-500/40 bg-gradient-to-br from-red-50 to-red-100/50 shadow-md";
      default:
        return "border-gray-200/60 bg-gradient-to-br from-gray-50 to-gray-50/80 shadow-sm hover:shadow-md hover:border-gray-300/60 transition-all";
    }
  }, [state]);

  const statusIcon = useMemo(() => {
    switch (state) {
      case "running":
        return <LoaderIcon className="size-3 animate-spin text-blue-600" />;
      case "completed":
        return <CheckCircle2Icon className="size-3 text-emerald-600" />;
      case "error":
        return <XCircleIcon className="size-3 text-red-600" />;
      default:
        return null;
    }
  }, [state]);

  return (
    <div className="flex items-center">
      <div
        className={`relative flex items-center gap-3 rounded-lg border px-4 py-2.5 transition-all duration-500 hover:scale-105 ${stateStyles}`}
        style={{
          animationDelay: `${index * 120}ms`,
        }}
      >
        {/* Stage icon with gradient background */}
        <div
          className={`flex size-8 items-center justify-center rounded-lg bg-gradient-to-br ${config.color} text-white shadow-lg flex-shrink-0 hover:scale-110 transition-transform`}
        >
          {config.icon}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[12px] font-bold text-foreground tracking-tight">
              {config.label}
            </span>
            {statusIcon}
          </div>
          <p className="text-[9px] text-foreground/70 leading-tight font-medium">
            {config.description}
          </p>
        </div>

        {/* Running glow ring */}
        {state === "running" && (
          <div className="absolute -inset-px rounded-xl animate-pipeline-glow pointer-events-none" />
        )}
      </div>

      {/* Connector arrow */}
      {!isLast && (
        <div className="relative mx-2 flex items-center">
          <div
            className={`h-[3px] w-6 transition-all duration-500 rounded-full ${
              state === "completed"
                ? "bg-gradient-to-r from-emerald-500 to-emerald-500/40 shadow-md"
                : state === "running"
                  ? "animate-pipeline-flow h-[3px] w-6 shadow-md"
                  : "bg-gray-300/40"
            }`}
          />
          <ChevronRightIcon
            className={`-ml-1.5 size-4 transition-all duration-500 font-bold ${
              state === "completed"
                ? "text-emerald-600"
                : state === "running"
                  ? "text-blue-600 animate-pulse"
                  : "text-gray-400"
            }`}
          />
        </div>
      )}
    </div>
  );
}

export function PipelineVisualization({
  checkpoints,
  stageStates,
  isProcessing,
  isCompleted,
  isError,
  activeIndex,
  route,
}: PipelineVisualizationProps) {
  const statusText = isError
    ? "Error en pipeline"
    : isCompleted
      ? "Pipeline completado"
      : isProcessing
        ? "Procesando..."
        : "En espera";

  const statusColor = isError
    ? "text-red-600"
    : isCompleted
      ? "text-emerald-600"
      : isProcessing
        ? "text-blue-600"
        : "text-foreground/60";

  return (
    <div className="glass rounded-2xl p-5 space-y-4 border border-gray-200/40 backdrop-blur-lg">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-gray-200/30">
        <div className="flex items-center gap-3">
          <div className="relative flex size-7 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-md">
            <DatabaseIcon className="size-4" />
            {isProcessing && (
              <div className="absolute inset-0 animate-orbit opacity-60">
                <div className="absolute -top-1 left-1/2 size-2 rounded-full bg-white/80" />
              </div>
            )}
          </div>
          <div>
            <span className="text-sm font-bold uppercase tracking-wider text-foreground">
              Agent Pipeline
            </span>
            <p className="text-[9px] text-foreground/60 font-medium">
              Real-time execution
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            variant="outline"
            className={`text-[10px] font-semibold px-3 py-1 shadow-sm ${
              route === "sql_pipeline"
                ? "border-blue-500/50 bg-gradient-to-r from-blue-50 to-blue-100/50 text-blue-700"
                : "border-purple-500/50 bg-gradient-to-r from-purple-50 to-purple-100/50 text-purple-700"
            }`}
          >
            {route === "sql_pipeline" ? "Nexus Insight" : "Chat"}
          </Badge>
          <div className="text-center">
            <span className={`text-xs font-bold ${statusColor}`}>
              {statusText}
            </span>
          </div>
        </div>
      </div>

      {/* Pipeline stages */}
      <div className="flex flex-wrap items-center gap-y-2">
        {checkpoints.map((checkpoint, index) => {
          const config = PIPELINE_STAGES[checkpoint] ?? {
            ...DEFAULT_CONFIG,
            label: checkpoint,
          };
          const state = stageStates[index] ?? "idle";
          return (
            <StageNode
              key={`${checkpoint}-${index}`}
              config={config}
              state={state}
              index={index}
              isLast={index === checkpoints.length - 1}
            />
          );
        })}
      </div>

      {/* Progress bar */}
      {isProcessing && (
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-gray-200/50 shadow-inner">
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-blue-600 via-purple-600 to-emerald-600 shadow-lg transition-all duration-700"
            style={{
              width: `${Math.max(5, ((activeIndex + 1) / Math.max(checkpoints.length, 1)) * 100)}%`,
            }}
          />
          <div className="absolute inset-0 animate-shimmer" />
        </div>
      )}

      {isCompleted && !isError && (
        <div className="h-2 w-full rounded-full shadow-md bg-gradient-to-r from-emerald-600 via-emerald-500 to-emerald-600" />
      )}

      {isError && (
        <div className="h-2 w-full rounded-full shadow-md bg-gradient-to-r from-red-600 via-red-500 to-red-600" />
      )}
    </div>
  );
}

/* ── Timeline Component ── */
interface TimelineEntry {
  label: string;
  ms: number;
}

interface ExecutionTimelineProps {
  stages: TimelineEntry[];
  totalMs?: number;
}

export function ExecutionTimeline({ stages, totalMs }: ExecutionTimelineProps) {
  const maxMs = useMemo(
    () => Math.max(...stages.map((s) => s.ms), 1),
    [stages],
  );

  if (stages.length === 0) {
    return (
      <div className="glass-subtle rounded-2xl p-5 border border-gray-200/40">
        <p className="text-[11px] font-bold uppercase tracking-wider text-foreground/70 mb-2">
          Execution Timeline
        </p>
        <p className="text-xs text-foreground/60 font-medium">
          Los timings aparecerán después de la primera respuesta.
        </p>
      </div>
    );
  }

  return (
    <div className="glass-subtle rounded-2xl p-5 space-y-3 border border-gray-200/40">
      <div className="flex items-center justify-between pb-2 border-b border-gray-200/30">
        <p className="text-[11px] font-bold uppercase tracking-wider text-foreground/70">
          Execution Timeline
        </p>
        {totalMs != null && (
          <Badge
            variant="outline"
            className="text-[10px] font-mono badge-glow bg-gradient-to-r from-blue-50 to-blue-100/50 border-blue-300/40 text-blue-700 font-bold shadow-sm"
          >
            {totalMs}ms total
          </Badge>
        )}
      </div>

      <div className="space-y-3">
        {stages.map((stage, i) => {
          const pct = (stage.ms / maxMs) * 100;
          const config = PIPELINE_STAGES[stage.label] ?? DEFAULT_CONFIG;

          return (
            <div
              key={`${stage.label}-${i}`}
              className="animate-slide-in-up"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-[12px] font-bold text-foreground">
                  {stage.label}
                </span>
                <span className="text-[11px] font-mono text-foreground/70 font-bold">
                  {stage.ms}ms
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-gray-200/50 overflow-hidden shadow-inner">
                <div
                  className={`h-full rounded-full bg-gradient-to-r ${config.color} transition-all duration-700 shadow-md`}
                  style={{ width: `${Math.max(3, pct)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Transparency Panel ── */
interface TransparencyPanelProps {
  question?: string;
  sql?: string;
  preview?: string;
  rowsReturned?: number;
  sqlRetries?: number;
  schemaSource?: string;
  schemaTablesCount?: number;
  fallback?: boolean;
  lastError?: string;
  subQueryCount?: number;
  subQueriesExecuted?: number;
  subQueriesFailed?: number;
  criticValidated?: boolean;
  sqlExecutionMs?: number;
  route: string;
}

export function TransparencyPanel({
  question,
  sql,
  preview,
  rowsReturned,
  schemaSource,
  schemaTablesCount,
  fallback,
  lastError,
  subQueryCount,
  subQueriesExecuted,
  subQueriesFailed,
  criticValidated,
  sqlExecutionMs,
  route,
}: TransparencyPanelProps) {
  return (
    <div className="glass-subtle rounded-2xl p-5 space-y-3 border border-gray-200/40">
      <div className="flex items-center justify-between pb-2 border-b border-gray-200/30">
        <p className="text-[11px] font-bold uppercase tracking-wider text-foreground/70">
          Transparencia
        </p>
        <Badge
          variant="outline"
          className={`text-[10px] font-semibold px-3 py-1 shadow-sm ${
            route === "sql_pipeline"
              ? "border-emerald-500/50 bg-gradient-to-r from-emerald-50 to-emerald-100/50 text-emerald-700"
              : "border-purple-500/50 bg-gradient-to-r from-purple-50 to-purple-100/50 text-purple-700"
          }`}
        >
          {route === "sql_pipeline" ? "SQL Pipeline" : "Chat"}
        </Badge>
      </div>

      {/* Question */}
      <div className="rounded-lg bg-gradient-to-br from-blue-50 to-blue-100/50 border border-blue-200/60 p-3 shadow-sm">
        <p className="text-[10px] font-bold text-blue-900 mb-1 uppercase tracking-wider">
          Pregunta Analizada
        </p>
        <p className="text-xs text-blue-800/90 line-clamp-3 font-medium">
          {question || "Sin pregunta registrada"}
        </p>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 gap-2">
        <MetricCard label="Filas" value={rowsReturned ?? "N/A"} />
        <MetricCard
          label="Sub-queries"
          value={
            subQueryCount != null
              ? `${subQueriesExecuted ?? 0}/${subQueryCount}`
              : "N/A"
          }
        />
        <MetricCard
          label="Schema"
          value={
            schemaSource
              ? `${schemaSource}${schemaTablesCount != null ? ` (${schemaTablesCount})` : ""}`
              : "N/A"
          }
        />
        <MetricCard
          label="Validación"
          value={
            criticValidated != null
              ? criticValidated
                ? "✅ OK"
                : "❌ Falló"
              : "N/A"
          }
        />
        <MetricCard label="SQL (ms)" value={sqlExecutionMs ?? "N/A"} />
        <MetricCard label="Fallback" value={fallback ? "Sí" : "No"} />
      </div>

      {/* Sub-query retry info */}
      {(subQueriesFailed ?? 0) > 0 && (
        <div className="rounded-lg bg-gradient-to-r from-amber-50 to-amber-100/50 border border-amber-300/50 p-2 shadow-sm">
          <p className="text-[10px] font-bold text-amber-900">
            ⚠️ {subQueriesFailed} sub-
            {subQueriesFailed === 1 ? "query" : "queries"} requirieron
            corrección
          </p>
        </div>
      )}

      {(subQueriesExecuted ?? 0) > 0 &&
        (subQueriesFailed ?? 0) === 0 &&
        (subQueryCount ?? 0) > 1 && (
          <div className="rounded-lg bg-gradient-to-r from-emerald-50 to-emerald-100/50 border border-emerald-300/50 p-2 shadow-sm">
            <p className="text-[10px] font-bold text-emerald-900">
              ✅ {subQueriesExecuted}/{subQueryCount} sub-queries exitosas
            </p>
          </div>
        )}

      {/* Error */}
      {lastError && (
        <div className="rounded-lg bg-gradient-to-r from-red-50 to-red-100/50 border border-red-300/50 p-2 shadow-sm">
          <p className="text-[10px] font-bold text-red-900 mb-1">
            ❌ Último error
          </p>
          <p className="text-[10px] text-red-800/80 line-clamp-3 font-medium">
            {lastError}
          </p>
        </div>
      )}

      {/* SQL Block */}
      <details className="group" open>
        <summary className="cursor-pointer text-[11px] font-bold text-foreground/70 flex items-center gap-2 mb-2 hover:text-foreground transition-colors">
          <ChevronRightIcon className="size-4 transition-transform group-open:rotate-90" />
          SQL Ejecutado
        </summary>
        <pre className="sql-block rounded-lg p-3 text-[11px] leading-5 max-h-36 overflow-auto whitespace-pre-wrap break-words border border-blue-200/50 bg-gradient-to-br from-blue-50 to-blue-50/80 text-blue-900 shadow-sm">
          {sql || (route === "chat_pipeline" ? "N/A en ruta Chat" : "Sin SQL")}
        </pre>
      </details>

      {/* Result Preview */}
      <details className="group">
        <summary className="cursor-pointer text-[11px] font-bold text-foreground/70 flex items-center gap-2 mb-2 hover:text-foreground transition-colors">
          <ChevronRightIcon className="size-4 transition-transform group-open:rotate-90" />
          Preview JSON
        </summary>
        <pre className="sql-block rounded-lg p-3 text-[10px] leading-5 max-h-32 overflow-auto whitespace-pre-wrap break-words border border-gray-200/50 bg-gradient-to-br from-gray-50 to-gray-50/80 text-foreground/70 shadow-sm">
          {preview || "Sin preview"}
        </pre>
      </details>
    </div>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-lg bg-gradient-to-br from-gray-50 to-gray-100/50 border border-gray-200/60 px-3 py-2 shadow-sm hover:shadow-md transition-all">
      <p className="text-[9px] text-foreground/70 uppercase tracking-wider font-bold">
        {label}
      </p>
      <p className="text-sm font-bold text-foreground mt-1 truncate">{value}</p>
    </div>
  );
}
