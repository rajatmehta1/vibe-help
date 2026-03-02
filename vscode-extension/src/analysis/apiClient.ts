import * as vscode from "vscode";
import {
  AnalyzeRequest,
  AnalyzeResponse,
  ApiError,
  ArchitectureResponse,
  AuthError,
  ConventionResponse,
  HealthResponse,
  IndexingJobResponse,
  NetworkError,
  PatternResponse,
  SimilarCodeResponse,
} from "../types";

export class ApiClient implements vscode.Disposable {
  private _outputChannel: vscode.OutputChannel;

  constructor(outputChannel: vscode.OutputChannel) {
    this._outputChannel = outputChannel;
  }

  // Settings read lazily so changes take effect immediately
  private get config() {
    return vscode.workspace.getConfiguration("forgeline");
  }

  private get serverUrl(): string {
    return this.config.get<string>("serverUrl", "http://localhost:8000");
  }

  private get apiKey(): string {
    return this.config.get<string>("apiKey", "");
  }

  private get projectId(): string {
    const id = this.config.get<string>("projectId", "");
    if (!id) {
      throw new ApiError(
        "Project ID not configured. Set forgeline.projectId in settings.",
        0,
      );
    }
    return id;
  }

  // ---- Core request method ----

  private async _request<T>(
    method: string,
    path: string,
    options: {
      body?: unknown;
      timeoutMs?: number;
      requiresAuth?: boolean;
      retries?: number;
      retryDelayMs?: number;
    } = {},
  ): Promise<T> {
    const {
      body,
      timeoutMs = 10_000,
      requiresAuth = true,
      retries = 1,
      retryDelayMs = 500,
    } = options;

    const url = `${this.serverUrl}${path}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (requiresAuth) {
      const key = this.apiKey;
      if (!key) {
        throw new AuthError(
          "API key not configured. Set forgeline.apiKey in settings.",
        );
      }
      headers["Authorization"] = `Bearer ${key}`;
    }

    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= retries; attempt++) {
      if (attempt > 0) {
        await new Promise((r) => setTimeout(r, retryDelayMs));
        this._log(`Retrying ${method} ${path} (attempt ${attempt + 1})`);
      }

      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        const response = await fetch(url, {
          method,
          headers,
          body: body ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (response.status === 401 || response.status === 403) {
          const detail = await this._safeJson(response);
          throw new AuthError(
            detail?.detail || "Authentication failed",
            response.status,
          );
        }

        if (!response.ok) {
          const detail = await this._safeJson(response);
          throw new ApiError(
            `API error: ${response.status} ${response.statusText}`,
            response.status,
            detail?.detail,
          );
        }

        return (await response.json()) as T;
      } catch (err) {
        // Don't retry auth or API errors — only network errors
        if (err instanceof AuthError || err instanceof ApiError) {
          throw err;
        }
        lastError = err instanceof Error ? err : new Error(String(err));
      }
    }

    throw new NetworkError(
      `Network error after ${retries + 1} attempts: ${lastError?.message ?? "unknown"}`,
      lastError,
    );
  }

  private async _safeJson(
    response: Response,
  ): Promise<Record<string, string> | null> {
    try {
      return (await response.json()) as Record<string, string>;
    } catch {
      return null;
    }
  }

  private _log(message: string): void {
    this._outputChannel.appendLine(`[ApiClient] ${message}`);
  }

  // ---- Public methods ----

  async healthCheck(): Promise<HealthResponse> {
    return this._request<HealthResponse>("GET", "/health", {
      timeoutMs: 5_000,
      requiresAuth: false,
    });
  }

  async analyze(request: AnalyzeRequest): Promise<AnalyzeResponse> {
    return this._request<AnalyzeResponse>(
      "POST",
      `/api/v1/projects/${this.projectId}/analyze`,
      { body: request, timeoutMs: 5_000 },
    );
  }

  async triggerIndex(
    type: "full" | "incremental" = "full",
  ): Promise<IndexingJobResponse> {
    const suffix = type === "incremental" ? "/incremental" : "";
    return this._request<IndexingJobResponse>(
      "POST",
      `/api/v1/projects/${this.projectId}/index${suffix}`,
      { timeoutMs: 10_000 },
    );
  }

  async getIndexStatus(): Promise<IndexingJobResponse> {
    return this._request<IndexingJobResponse>(
      "GET",
      `/api/v1/projects/${this.projectId}/index/status`,
    );
  }

  async getPatterns(type?: string): Promise<PatternResponse> {
    const query = type ? `?type=${encodeURIComponent(type)}` : "";
    return this._request<PatternResponse>(
      "GET",
      `/api/v1/projects/${this.projectId}/patterns${query}`,
    );
  }

  async getConventions(category?: string): Promise<ConventionResponse> {
    const query = category
      ? `?category=${encodeURIComponent(category)}`
      : "";
    return this._request<ConventionResponse>(
      "GET",
      `/api/v1/projects/${this.projectId}/conventions${query}`,
    );
  }

  async getArchitecture(): Promise<ArchitectureResponse> {
    return this._request<ArchitectureResponse>(
      "GET",
      `/api/v1/projects/${this.projectId}/architecture`,
    );
  }

  async findSimilarCode(
    code: string,
    language: string,
    limit: number = 5,
  ): Promise<SimilarCodeResponse> {
    return this._request<SimilarCodeResponse>(
      "POST",
      `/api/v1/projects/${this.projectId}/similar`,
      { body: { code, language, limit } },
    );
  }

  async triggerLearning(): Promise<{ status: string; message: string }> {
    return this._request<{ status: string; message: string }>(
      "POST",
      `/api/v1/projects/${this.projectId}/learn`,
    );
  }

  async getKnowledgeStats(): Promise<Record<string, unknown>> {
    return this._request<Record<string, unknown>>(
      "GET",
      `/api/v1/projects/${this.projectId}/knowledge/stats`,
    );
  }

  dispose(): void {
    // No resources to clean up currently
  }
}
