import { useState, useMemo } from "react";
import { useProject } from "@/contexts/ProjectContext";
import { useApi } from "@/hooks/useApi";
import { scanService } from "@/services/scanService";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import ScanFilters from "@/components/scans/ScanFilters";
import type { Filters } from "@/components/scans/ScanFilters";
import ScanHistoryTable from "@/components/scans/ScanHistoryTable";
import { exportScansToCsv } from "@/lib/csvExport";
import { History } from "lucide-react";

export default function ScanHistory() {
  const { currentProject } = useProject();
  const projectId = currentProject?.id;

  const { data: scans, isLoading } = useApi(
    () => (projectId ? scanService.list(projectId) : Promise.resolve([])),
    [projectId],
  );

  const [filters, setFilters] = useState<Filters>({
    scanType: "all",
    status: "all",
    dateFrom: "",
    dateTo: "",
  });

  const filteredScans = useMemo(() => {
    if (!scans) return [];
    return scans.filter((s) => {
      if (filters.scanType !== "all" && s.scan_type !== filters.scanType)
        return false;
      if (filters.status !== "all" && s.status !== filters.status) return false;
      if (filters.dateFrom && s.started_at) {
        if (s.started_at < filters.dateFrom) return false;
      }
      if (filters.dateTo && s.started_at) {
        if (s.started_at > filters.dateTo + "T23:59:59") return false;
      }
      return true;
    });
  }, [scans, filters]);

  if (!currentProject) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="text-center">
          <History className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h2 className="text-xl font-semibold">Scan History</h2>
          <p className="mt-2 text-muted-foreground">
            Select a project to view scan history.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Scan History</h1>

      <ScanFilters
        filters={filters}
        onFiltersChange={setFilters}
        onExport={() => exportScansToCsv(filteredScans)}
        hasData={filteredScans.length > 0}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Scans{" "}
            {!isLoading && (
              <span className="text-muted-foreground font-normal">
                ({filteredScans.length})
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10" />
              ))}
            </div>
          ) : (
            <ScanHistoryTable scans={filteredScans} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
