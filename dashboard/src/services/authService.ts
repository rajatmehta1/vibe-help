import type { AuthResponse, LoginRequest, UserCreate, UserResponse } from "@/types";
import apiClient from "./apiClient";

export const authService = {
  async login(data: LoginRequest): Promise<AuthResponse> {
    const res = await apiClient.post<AuthResponse>("/auth/login", data);
    return res.data;
  },

  async register(data: UserCreate): Promise<AuthResponse> {
    const res = await apiClient.post<AuthResponse>("/auth/register", data);
    return res.data;
  },

  async getMe(): Promise<UserResponse> {
    const res = await apiClient.get<UserResponse>("/auth/me");
    return res.data;
  },
};
