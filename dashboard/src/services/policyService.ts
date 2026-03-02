import type {
  PolicyCreateRequest,
  PolicyDetailResponse,
  PolicyResponse,
  PolicyTemplateResponse,
  PolicyUpdate,
} from "@/types";
import apiClient from "./apiClient";

export const policyService = {
  async listBuiltin(): Promise<PolicyTemplateResponse[]> {
    const res = await apiClient.get<PolicyTemplateResponse[]>(
      "/policies/builtin",
    );
    return res.data;
  },

  async list(projectId: string): Promise<PolicyResponse[]> {
    const res = await apiClient.get<PolicyResponse[]>(
      `/projects/${projectId}/policies`,
    );
    return res.data;
  },

  async get(
    projectId: string,
    policyId: string,
  ): Promise<PolicyDetailResponse> {
    const res = await apiClient.get<PolicyDetailResponse>(
      `/projects/${projectId}/policies/${policyId}`,
    );
    return res.data;
  },

  async create(
    projectId: string,
    data: PolicyCreateRequest,
  ): Promise<PolicyResponse> {
    const res = await apiClient.post<PolicyResponse>(
      `/projects/${projectId}/policies`,
      data,
    );
    return res.data;
  },

  async update(
    projectId: string,
    policyId: string,
    data: PolicyUpdate,
  ): Promise<PolicyResponse> {
    const res = await apiClient.put<PolicyResponse>(
      `/projects/${projectId}/policies/${policyId}`,
      data,
    );
    return res.data;
  },

  async delete(projectId: string, policyId: string): Promise<void> {
    await apiClient.delete(`/projects/${projectId}/policies/${policyId}`);
  },
};
