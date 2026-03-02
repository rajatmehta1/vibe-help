import apiClient from "./apiClient";
import type { ScanResponse } from "@/types";

export const scanService = {
  async list(projectId: string): Promise<ScanResponse[]> {
    try {
      const { data } = await apiClient.get<ScanResponse[]>(
        `/projects/${projectId}/scans`,
      );
      return data;
    } catch (err: unknown) {
      // Endpoint may not exist yet — return empty gracefully
      if (
        typeof err === "object" &&
        err !== null &&
        "response" in err &&
        typeof (err as { response?: { status?: number } }).response?.status ===
          "number" &&
        (err as { response: { status: number } }).response.status === 404
      ) {
        return [];
      }
      throw err;
    }
  },
};
