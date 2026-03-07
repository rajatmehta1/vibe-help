import apiClient from "./apiClient";
import type { ScanResponse } from "@/types";

interface ScanStatusResponse {
  id: string;
  status: string;
  total_violations: number;
  started_at: string | null;
  completed_at: string | null;
  metadata_: Record<string, unknown> | null;
}

export interface ViolationRecord {
  id: string;
  file_path: string;
  line_start: number;
  line_end: number;
  column_start: number;
  column_end: number;
  severity: string;
  message: string;
  suggestion: string | null;
  code_snippet: string | null;
}

export const scanService = {
  async list(projectId: string): Promise<ScanResponse[]> {
    try {
      const { data } = await apiClient.get<ScanResponse[]>(
        `/projects/${projectId}/scans`,
      );
      return data;
    } catch (err: unknown) {
      if (
        typeof err === "object" &&
        err !== null &&
        "response" in err &&
        (err as { response: { status: number } }).response.status === 404
      ) {
        return [];
      }
      throw err;
    }
  },

  async triggerBulkScan(
    projectId: string,
  ): Promise<{ scan_id: string; status: string; message: string }> {
    const { data } = await apiClient.post(
      `/projects/${projectId}/scan`,
    );
    return data;
  },

  async getScanStatus(projectId: string): Promise<ScanStatusResponse> {
    const { data } = await apiClient.get<ScanStatusResponse>(
      `/projects/${projectId}/scan/status`,
    );
    return data;
  },

  async getViolations(projectId: string, scanId: string): Promise<ViolationRecord[]> {
    const { data } = await apiClient.get<ViolationRecord[]>(
      `/projects/${projectId}/scans/${scanId}/violations`,
    );
    return data;
  },

  async getStats(projectId: string): Promise<{
    total_violations: number;
    scans_over_time: { date: string; total: number }[];
    top_policies: { name: string; violations: number }[];
    recent_activity: {
      id: string;
      project_id: string;
      user_id: string | null;
      action: string;
      details: Record<string, unknown> | null;
      ip_address: string | null;
      created_at: string;
    }[];
  }> {
    const { data } = await apiClient.get(`/projects/${projectId}/stats`);
    return data;
  },
};
