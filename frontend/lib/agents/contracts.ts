export type AgentIntent =
  | "architecture"
  | "performance"
  | "security"
  | "frontend"
  | "backend"
  | "general";

export interface AgentInput {
  text: string;
  locale?: string;
}

export interface AgentContext {
  intent: AgentIntent;
  focusAreas: string[];
  riskLevel: "low" | "medium" | "high";
}

export interface AgentResult {
  content: string;
  checkpoints: string[];
}
