import { useState, useCallback } from "react";
import type { ScanResponse } from "@/types";
import { useProject } from "@/contexts/ProjectContext";
import { scanService, type ViolationRecord } from "@/services/scanService";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/formatters";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";

interface Props {
  scans: ScanResponse[];
}

function statusVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "completed":
      return "default";
    case "running":
      return "secondary";
    case "failed":
      return "destructive";
    default:
      return "outline";
  }
}

function severityVariant(
  severity: string,
): "default" | "secondary" | "destructive" | "outline" {
  switch (severity) {
    case "critical":
    case "high":
      return "destructive";
    case "medium":
      return "secondary";
    default:
      return "outline";
  }
}

function typeLabel(t: string): string {
  return t
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export default function ScanHistoryTable({ scans }: Props) {
  const { currentProject } = useProject();
  const projectId = currentProject?.id;

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [violations, setViolations] = useState<Record<string, ViolationRecord[]>>({});
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const handleToggle = useCallback(async (scanId: string) => {
    if (expandedId === scanId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(scanId);
    if (!violations[scanId] && projectId) {
      setLoadingId(scanId);
      try {
        const data = await scanService.getViolations(projectId, scanId);
        setViolations((prev) => ({ ...prev, [scanId]: data }));
      } catch {
        setViolations((prev) => ({ ...prev, [scanId]: [] }));
      } finally {
        setLoadingId(null);
      }
    }
  }, [expandedId, violations, projectId]);

  if (scans.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No scans found. Scans will appear here after they are triggered.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-8" />
          <TableHead>Date</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Violations</TableHead>
          <TableHead>Trigger</TableHead>
          <TableHead>File Path</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {scans.map((scan) => {
          const isExpanded = expandedId === scan.id;
          const scanViolations = violations[scan.id];
          const isLoading = loadingId === scan.id;
          return (
            <>
              <TableRow
                key={scan.id}
                className="cursor-pointer"
                onClick={() => handleToggle(scan.id)}
              >
                <TableCell className="px-2">
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </TableCell>
                <TableCell className="whitespace-nowrap text-sm">
                  {scan.started_at
                    ? formatDateTime(scan.started_at)
                    : "—"}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{typeLabel(scan.scan_type)}</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={statusVariant(scan.status)}>
                    {scan.status}
                  </Badge>
                </TableCell>
                <TableCell>{scan.total_violations}</TableCell>
                <TableCell className="text-sm">{scan.trigger_source}</TableCell>
                <TableCell className="max-w-[200px] truncate text-sm text-muted-foreground">
                  {scan.file_path ?? "—"}
                </TableCell>
              </TableRow>
              {isExpanded && (
                <TableRow key={`${scan.id}-detail`}>
                  <TableCell colSpan={7} className="bg-muted/50 px-4 py-4">
                    {/* Scan metadata */}
                    <div className="mb-4 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
                      <div>
                        <span className="text-muted-foreground">Started: </span>
                        {scan.started_at ? formatDateTime(scan.started_at) : "—"}
                      </div>
                      <div>
                        <span className="text-muted-foreground">Completed: </span>
                        {scan.completed_at ? formatDateTime(scan.completed_at) : "—"}
                      </div>
                      <div>
                        <span className="text-muted-foreground">Files scanned: </span>
                        {(scan.metadata_ as Record<string, number> | null)?.files_scanned ?? "—"}
                      </div>
                      <div>
                        <span className="text-muted-foreground">Scan ID: </span>
                        <code className="text-xs">{scan.id.slice(0, 8)}…</code>
                      </div>
                    </div>

                    {/* Violations */}
                    {isLoading ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Loading violations…
                      </div>
                    ) : scanViolations && scanViolations.length > 0 ? (
                      <div className="overflow-x-auto rounded border">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>File</TableHead>
                              <TableHead>Line</TableHead>
                              <TableHead>Severity</TableHead>
                              <TableHead>Message</TableHead>
                              <TableHead>Suggestion</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {scanViolations.map((v) => (
                              <TableRow key={v.id}>
                                <TableCell className="max-w-[200px] truncate font-mono text-xs">
                                  {v.file_path}
                                </TableCell>
                                <TableCell className="text-xs text-muted-foreground">
                                  {v.line_start === v.line_end
                                    ? v.line_start
                                    : `${v.line_start}–${v.line_end}`}
                                </TableCell>
                                <TableCell>
                                  <Badge
                                    variant={severityVariant(v.severity)}
                                    className="text-xs"
                                  >
                                    {v.severity}
                                  </Badge>
                                </TableCell>
                                <TableCell className="max-w-[300px] text-xs">
                                  {v.message}
                                </TableCell>
                                <TableCell className="max-w-[250px] text-xs text-muted-foreground">
                                  {v.suggestion ?? "—"}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    ) : scanViolations && scanViolations.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No violations found in this scan.</p>
                    ) : scan.status !== "completed" ? (
                      <p className="text-sm text-muted-foreground">Scan has not completed yet.</p>
                    ) : null}
                  </TableCell>
                </TableRow>
              )}
            </>
          );
        })}
      </TableBody>
    </Table>
  );
}
