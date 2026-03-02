import type { ScanType, ScanStatus } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Download } from "lucide-react";

interface Filters {
  scanType: ScanType | "all";
  status: ScanStatus | "all";
  dateFrom: string;
  dateTo: string;
}

interface Props {
  filters: Filters;
  onFiltersChange: (filters: Filters) => void;
  onExport: () => void;
  hasData: boolean;
}

const scanTypes: { value: ScanType | "all"; label: string }[] = [
  { value: "all", label: "All Types" },
  { value: "realtime", label: "Realtime" },
  { value: "file", label: "File" },
  { value: "workspace", label: "Workspace" },
];

const statuses: { value: ScanStatus | "all"; label: string }[] = [
  { value: "all", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

export default function ScanFilters({
  filters,
  onFiltersChange,
  onExport,
  hasData,
}: Props) {
  return (
    <div className="flex flex-wrap items-end gap-4">
      <div className="space-y-1">
        <Label className="text-xs">Type</Label>
        <Select
          value={filters.scanType}
          onValueChange={(v) =>
            onFiltersChange({ ...filters, scanType: v as ScanType | "all" })
          }
        >
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {scanTypes.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label className="text-xs">Status</Label>
        <Select
          value={filters.status}
          onValueChange={(v) =>
            onFiltersChange({ ...filters, status: v as ScanStatus | "all" })
          }
        >
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {statuses.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label className="text-xs">From</Label>
        <Input
          type="date"
          value={filters.dateFrom}
          onChange={(e) =>
            onFiltersChange({ ...filters, dateFrom: e.target.value })
          }
          className="w-36"
        />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">To</Label>
        <Input
          type="date"
          value={filters.dateTo}
          onChange={(e) =>
            onFiltersChange({ ...filters, dateTo: e.target.value })
          }
          className="w-36"
        />
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={onExport}
        disabled={!hasData}
      >
        <Download className="mr-2 h-4 w-4" />
        Export CSV
      </Button>
    </div>
  );
}

export type { Filters };
