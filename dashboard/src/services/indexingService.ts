import type { IndexingJobResponse } from "@/types";
import apiClient from "./apiClient";

export const indexingService = {
  async triggerFull(projectId: string): Promise<IndexingJobResponse> {
    const res = await apiClient.post<IndexingJobResponse>(
      `/projects/${projectId}/index`,
    );
    return res.data;
  },

  async triggerIncremental(projectId: string): Promise<IndexingJobResponse> {
    const res = await apiClient.post<IndexingJobResponse>(
      `/projects/${projectId}/index/incremental`,
    );
    return res.data;
  },

  async getStatus(projectId: string): Promise<IndexingJobResponse> {
    const res = await apiClient.get<IndexingJobResponse>(
      `/projects/${projectId}/index/status`,
    );
    return res.data;
  },

  async getKnowledgeStats(
    projectId: string,
  ): Promise<Record<string, unknown>> {
    const res = await apiClient.get<Record<string, unknown>>(
      `/projects/${projectId}/knowledge/stats`,
    );
    return res.data;
  },
};
