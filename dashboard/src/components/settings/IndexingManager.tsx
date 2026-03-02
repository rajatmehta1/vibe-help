import { useState, useCallback, useEffect, useRef } from "react";
import { useProject } from "@/contexts/ProjectContext";
import { indexingService } from "@/services/indexingService";
import type { IndexingJobResponse } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Database, RefreshCw } from "lucide-react";

export default function IndexingManager() {
  const { currentProject } = useProject();
  const projectId = currentProject?.id;

  const [status, setStatus] = useState<IndexingJobResponse | null>(null);
  const [triggering, setTriggering] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await indexingService.getStatus(projectId);
      setStatus(res);
    } catch {
      // Status endpoint may not exist yet
      setStatus(null);
    }
  }, [projectId]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Auto-refresh when job is running
  useEffect(() => {
    if (status?.status === "pending" || status?.status === "running") {
      intervalRef.current = setInterval(fetchStatus, 3000);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [status?.status, fetchStatus]);

  const handleTrigger = useCallback(
    async (type: "full" | "incremental") => {
      if (!projectId) return;
      setTriggering(true);
      try {
        const job =
          type === "full"
            ? await indexingService.triggerFull(projectId)
            : await indexingService.triggerIncremental(projectId);
        setStatus(job);
        toast.success(`${type === "full" ? "Full" : "Incremental"} indexing started`);
      } catch {
        toast.error("Failed to start indexing");
      } finally {
        setTriggering(false);
      }
    },
    [projectId],
  );

  const isRunning = status?.status === "pending" || status?.status === "running";
  const progress =
    status && status.total_files > 0
      ? Math.round((status.processed_files / status.total_files) * 100)
      : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Database className="h-4 w-4" />
          Indexing
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {status && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge
                variant={
                  status.status === "completed"
                    ? "default"
                    : status.status === "failed"
                      ? "destructive"
                      : "secondary"
                }
              >
                {status.status}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {status.job_type} index
              </span>
              {isRunning && (
                <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
              )}
            </div>
            {isRunning && (
              <div className="space-y-1">
                <Progress value={progress} className="h-2" />
                <p className="text-xs text-muted-foreground">
                  {status.processed_files} / {status.total_files} files processed
                </p>
              </div>
            )}
            {status.error_message && (
              <p className="text-sm text-destructive">{status.error_message}</p>
            )}
          </div>
        )}
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => handleTrigger("full")}
            disabled={triggering || isRunning}
          >
            Full Index
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => handleTrigger("incremental")}
            disabled={triggering || isRunning}
          >
            Incremental Index
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
