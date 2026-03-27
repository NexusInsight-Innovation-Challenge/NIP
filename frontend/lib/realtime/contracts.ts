export interface RealtimeNegotiateResponse {
  url: string;
  hub: string;
  group: string;
  userId: string;
}

export interface RealtimeMessageRequest {
  sessionId: string;
  text: string;
}

export type RealtimeServerEvent =
  | {
      type: "status";
      status: "queued" | "processing" | "completed" | "error";
      message?: string;
      timestamp: string;
    }
  | {
      type: "assistant-token";
      token: string;
      timestamp: string;
    }
  | {
      type: "assistant-complete";
      content: string;
      checkpoints: string[];
      timestamp: string;
      intent?: string;
      route?: string;
      processingMs?: number;
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
      // New v2 fields
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
  | {
      type: "approval-required";
      correlationId: string;
      message: string;
      reason?: string;
      categories?: string[];
      riskLevel?: string;
      timeoutSeconds: number;
      requestedAt?: string;
      expiresAt?: string;
      analysisQuestion?: string;
      validatedSql?: string;
      timestamp: string;
    }
  | {
      type: "approval-finalized";
      correlationId: string;
      approved: boolean;
      status: "approved" | "rejected" | "expired";
      decidedAt?: string;
      decidedBy?: string;
      reason?: string;
      timestamp: string;
    };
