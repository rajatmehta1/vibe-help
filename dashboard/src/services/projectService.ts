import type {
  ProjectCreate,
  ProjectDetailResponse,
  ProjectResponse,
  ProjectUpdate,
} from "@/types";
import apiClient from "./apiClient";

export const projectService = {
  async list(): Promise<ProjectResponse[]> {
    const res = await apiClient.get<ProjectResponse[]>("/projects/");
    return res.data;
  },

  async get(id: string): Promise<ProjectDetailResponse> {
    const res = await apiClient.get<ProjectDetailResponse>(`/projects/${id}`);
    return res.data;
  },

  async create(data: ProjectCreate): Promise<ProjectResponse> {
    const res = await apiClient.post<ProjectResponse>("/projects/", data);
    return res.data;
  },

  async update(id: string, data: ProjectUpdate): Promise<ProjectResponse> {
    const res = await apiClient.put<ProjectResponse>(`/projects/${id}`, data);
    return res.data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/projects/${id}`);
  },
};
