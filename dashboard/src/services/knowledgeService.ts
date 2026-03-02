import type {
  ArchitectureResponse,
  ConventionsResponse,
  PatternsResponse,
  SimilarCodeRequest,
  SimilarCodeResult,
} from "@/types";
import apiClient from "./apiClient";

export const knowledgeService = {
  async listPatterns(
    projectId: string,
    type?: string,
  ): Promise<PatternsResponse> {
    const params = type ? { type } : undefined;
    const res = await apiClient.get<PatternsResponse>(
      `/projects/${projectId}/patterns`,
      { params },
    );
    return res.data;
  },

  async getPatternEvidence(
    projectId: string,
    patternId: string,
  ): Promise<{ pattern_id: string; evidence: unknown[]; count: number }> {
    const res = await apiClient.get(
      `/projects/${projectId}/patterns/${patternId}/evidence`,
    );
    return res.data;
  },

  async listConventions(
    projectId: string,
    category?: string,
  ): Promise<ConventionsResponse> {
    const params = category ? { category } : undefined;
    const res = await apiClient.get<ConventionsResponse>(
      `/projects/${projectId}/conventions`,
      { params },
    );
    return res.data;
  },

  async getArchitecture(projectId: string): Promise<ArchitectureResponse> {
    const res = await apiClient.get<ArchitectureResponse>(
      `/projects/${projectId}/architecture`,
    );
    return res.data;
  },

  async findSimilar(
    projectId: string,
    data: SimilarCodeRequest,
  ): Promise<{ results: SimilarCodeResult[]; count: number }> {
    const res = await apiClient.post(
      `/projects/${projectId}/similar`,
      data,
    );
    return res.data;
  },

  async triggerLearning(
    projectId: string,
  ): Promise<{ status: string; message: string }> {
    const res = await apiClient.post(`/projects/${projectId}/learn`);
    return res.data;
  },
};
