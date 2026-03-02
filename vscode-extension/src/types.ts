// ---- Backend API Response Types ----

export interface HealthResponse {
  status: string;
  service: string;
  neo4j: string;
}

export interface IndexingJobResponse {
  id: string;
  project_id: string;
  status: ScanStatus;
  job_type: IndexingJobType;
  total_files: number;
  processed_files: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ViolationResponse {
  id: string;
  scan_id: string;
  policy_id: string;
  severity: SeverityLevel;
  file_path: string;
  line_start: number;
  line_end: number;
  column_start: number;
  column_end: number;
  message: string;
  suggestion: string | null;
  context_evidence: Record<string, unknown> | null;
  auto_fix: AutoFix | null;
  code_snippet: string | null;
  created_at: string;
}

export interface AutoFix {
  type: "rename" | "replace" | "insert";
  new_name?: string;
  replacement?: string;
  insert_text?: string;
  insert_position?: "before" | "after";
}

export interface PatternResponse {
  patterns: Pattern[];
  count: number;
}

export interface Pattern {
  id: string;
  category: string;
  name: string;
  description: string;
  confidence: number;
  [key: string]: unknown;
}

export interface ConventionResponse {
  conventions: Convention[];
  count: number;
}

export interface Convention {
  id: string;
  category: string;
  name: string;
  description: string;
  [key: string]: unknown;
}

export interface ArchitectureResponse {
  layers: ArchitectureLayer[];
  cross_layer_relationships: CrossLayerRelationship[];
}

export interface ArchitectureLayer {
  name: string;
  description: string;
  modules: string[];
  module_count: number;
}

export interface CrossLayerRelationship {
  from_layer: string;
  to_layer: string;
  count: number;
}

export interface SimilarCodeResponse {
  results: SimilarCodeResult[];
  count: number;
}

export interface SimilarCodeResult {
  file_path: string;
  code_unit_name: string;
  code_unit_type: string;
  similarity_score: number;
  language: string;
}

export interface AnalyzeRequest {
  code: string;
  file_path: string;
  language: string;
  surrounding_context?: string;
}

export interface AnalyzeResponse {
  violations: ViolationResponse[];
  scan_id: string;
}

// ---- Enums ----

export type SeverityLevel = "error" | "warning" | "info";
export type ScanStatus = "pending" | "running" | "completed" | "failed";
export type ScanType = "realtime" | "file" | "workspace";
export type IndexingJobType = "full" | "incremental";

// ---- Extension-local types ----

export type ChangeType = "paste" | "rapid_sequence" | "manual";

export interface ChangeMetadata {
  filePath: string;
  insertedText: string;
  lineStart: number;
  lineEnd: number;
  timestamp: number;
  changeType: ChangeType;
  characterCount: number;
}

export interface AIDetectionResult {
  confidence: number;
  signals: string[];
  isLikelyAI: boolean;
}

// ---- Webview message types ----

export type WebviewMessage =
  | { type: "goToLine"; line: number }
  | { type: "suppress"; policyId: string; line: number };

// ---- Error types ----

export class ForgeLineError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ForgeLineError";
  }
}

export class NetworkError extends ForgeLineError {
  constructor(
    message: string,
    public readonly cause?: Error,
  ) {
    super(message);
    this.name = "NetworkError";
  }
}

export class AuthError extends ForgeLineError {
  public readonly statusCode: number;
  constructor(message: string, statusCode: number = 401) {
    super(message);
    this.name = "AuthError";
    this.statusCode = statusCode;
  }
}

export class ApiError extends ForgeLineError {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly detail?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
