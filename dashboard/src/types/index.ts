// ---- Enums ----

export type PolicyCategory =
  | "security"
  | "naming"
  | "architecture"
  | "error_handling"
  | "dependencies"
  | "performance"
  | "documentation"
  | "custom";

export type SeverityLevel = "error" | "warning" | "info";
export type ScanStatus = "pending" | "running" | "completed" | "failed";
export type ScanType = "realtime" | "file" | "workspace";
export type IndexingJobType = "full" | "incremental";
export type CodeUnitType = "function" | "class" | "module" | "file";
export type AuditAction =
  | "code_detected"
  | "scan_started"
  | "scan_completed"
  | "policy_created"
  | "policy_updated"
  | "index_started"
  | "index_completed";

// ---- Auth ----

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AuthResponse {
  user: UserResponse;
  token: TokenResponse;
}

// ---- Projects ----

export interface ProjectCreate {
  name: string;
  description?: string;
  root_path?: string;
  primary_language?: string;
  settings?: Record<string, unknown>;
}

export interface ProjectUpdate {
  name?: string;
  slug?: string;
  description?: string;
  root_path?: string;
  primary_language?: string;
  settings?: Record<string, unknown>;
}

export interface ProjectResponse {
  id: string;
  org_id: string;
  name: string;
  slug: string;
  description: string | null;
  root_path: string | null;
  primary_language: string | null;
  settings: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  last_indexed_at: string | null;
}

export interface ProjectDetailResponse extends ProjectResponse {
  policy_count: number;
  last_scan_at: string | null;
  last_indexed_at_str: string | null;
}

// ---- Policies ----

export interface PolicyCreateRequest {
  policy_template_id?: string;
  name: string;
  description?: string;
  category: PolicyCategory;
  severity_default: SeverityLevel;
  is_active?: boolean;
  configuration?: Record<string, unknown>;
}

export interface PolicyUpdate {
  name?: string;
  description?: string;
  category?: PolicyCategory;
  severity_default?: SeverityLevel;
  is_active?: boolean;
  configuration?: Record<string, unknown>;
}

export interface PolicyResponse {
  id: string;
  project_id: string;
  policy_template_id: string | null;
  name: string;
  description: string | null;
  category: PolicyCategory;
  severity_default: SeverityLevel;
  is_active: boolean;
  configuration: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface PolicyDetailResponse extends PolicyResponse {
  violation_count: number;
}

export interface PolicyTemplateResponse {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  category: PolicyCategory;
  default_severity: SeverityLevel;
  default_configuration: Record<string, unknown> | null;
  is_builtin: boolean;
  version: string | null;
  created_at: string;
}

// ---- Scans ----

export interface ScanResponse {
  id: string;
  project_id: string;
  scan_type: ScanType;
  status: ScanStatus;
  file_path: string | null;
  trigger_source: string;
  total_violations: number;
  started_at: string | null;
  completed_at: string | null;
  metadata_: Record<string, unknown> | null;
}

// ---- Violations ----

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
  auto_fix: Record<string, unknown> | null;
  code_snippet: string | null;
  created_at: string;
}

// ---- Indexing ----

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

// ---- Knowledge ----

export interface PatternItem {
  id: string;
  category: string;
  name: string;
  description: string;
  confidence: number;
  [key: string]: unknown;
}

export interface PatternsResponse {
  patterns: PatternItem[];
  count: number;
}

export interface ConventionItem {
  id: string;
  category: string;
  name: string;
  description: string;
  [key: string]: unknown;
}

export interface ConventionsResponse {
  conventions: ConventionItem[];
  count: number;
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

export interface ArchitectureResponse {
  layers: ArchitectureLayer[];
  cross_layer_relationships: CrossLayerRelationship[];
}

export interface SimilarCodeRequest {
  code: string;
  language: string;
  limit?: number;
}

export interface SimilarCodeResult {
  file_path: string;
  code_unit_name: string;
  code_unit_type: string;
  similarity_score: number;
  language: string;
}

// ---- Audit ----

export interface AuditLogResponse {
  id: string;
  project_id: string;
  user_id: string | null;
  action: AuditAction;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}
