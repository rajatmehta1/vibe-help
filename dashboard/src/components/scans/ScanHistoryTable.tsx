import { useState } from "react";
import type { ScanResponse } from "@/types";
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
import { ChevronDown, ChevronRight } from "lucide-react";

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

function typeLabel(t: string): string {
  return t
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export default function ScanHistoryTable({ scans }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

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
          return (
            <>
              <TableRow
                key={scan.id}
                className="cursor-pointer"
                onClick={() =>
                  setExpandedId(isExpanded ? null : scan.id)
                }
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
                  <TableCell colSpan={7} className="bg-muted/50 px-8 py-4">
                    <div className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
                      <div>
                        <span className="text-muted-foreground">
                          Started:{" "}
                        </span>
                        {scan.started_at
                          ? formatDateTime(scan.started_at)
                          : "—"}
                      </div>
                      <div>
                        <span className="text-muted-foreground">
                          Completed:{" "}
                        </span>
                        {scan.completed_at
                          ? formatDateTime(scan.completed_at)
                          : "—"}
                      </div>
                      <div>
                        <span className="text-muted-foreground">
                          Scan ID:{" "}
                        </span>
                        <code className="text-xs">{scan.id}</code>
                      </div>
                      {scan.metadata_ && (
                        <div>
                          <span className="text-muted-foreground">
                            Metadata:{" "}
                          </span>
                          <code className="text-xs">
                            {JSON.stringify(scan.metadata_)}
                          </code>
                        </div>
                      )}
                    </div>
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
