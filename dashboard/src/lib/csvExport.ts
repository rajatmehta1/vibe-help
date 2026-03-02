import type { ScanResponse } from "@/types";

export function exportScansToCsv(scans: ScanResponse[]): void {
  const headers = [
    "ID",
    "Type",
    "Status",
    "Violations",
    "Trigger",
    "File Path",
    "Started At",
    "Completed At",
  ];

  const rows = scans.map((s) => [
    s.id,
    s.scan_type,
    s.status,
    String(s.total_violations),
    s.trigger_source,
    s.file_path ?? "",
    s.started_at ?? "",
    s.completed_at ?? "",
  ]);

  const csv = [headers, ...rows]
    .map((row) =>
      row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","),
    )
    .join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `scans-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
