import { useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useProject } from "@/contexts/ProjectContext";
import { useApi } from "@/hooks/useApi";
import { policyService } from "@/services/policyService";
import type { SeverityLevel } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import {
  categoryLabel,
  severityBadgeVariant,
  formatDate,
} from "@/lib/formatters";
import { ChevronLeft, Trash2 } from "lucide-react";

const severities: SeverityLevel[] = ["error", "warning", "info"];

export default function PolicyDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentProject } = useProject();
  const projectId = currentProject?.id;

  const {
    data: policy,
    isLoading,
    refetch,
  } = useApi(
    () =>
      projectId && id
        ? policyService.get(projectId, id)
        : Promise.resolve(null),
    [projectId, id],
  );

  const [configText, setConfigText] = useState<string | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const currentConfig =
    configText ??
    (policy?.configuration
      ? JSON.stringify(policy.configuration, null, 2)
      : "");

  const handleSeverityChange = useCallback(
    async (severity: SeverityLevel) => {
      if (!projectId || !id) return;
      try {
        await policyService.update(projectId, id, {
          severity_default: severity,
        });
        refetch();
        toast.success("Severity updated");
      } catch {
        toast.error("Failed to update severity");
      }
    },
    [projectId, id, refetch],
  );

  const handleToggle = useCallback(
    async (isActive: boolean) => {
      if (!projectId || !id) return;
      try {
        await policyService.update(projectId, id, { is_active: isActive });
        refetch();
      } catch {
        toast.error("Failed to update policy");
      }
    },
    [projectId, id, refetch],
  );

  const handleSaveConfig = useCallback(async () => {
    if (!projectId || !id) return;
    setSavingConfig(true);
    try {
      const configuration = currentConfig.trim()
        ? JSON.parse(currentConfig)
        : null;
      await policyService.update(projectId, id, { configuration });
      setConfigText(null);
      refetch();
      toast.success("Configuration saved");
    } catch (err) {
      if (err instanceof SyntaxError) {
        toast.error("Invalid JSON");
      } else {
        toast.error("Failed to save configuration");
      }
    } finally {
      setSavingConfig(false);
    }
  }, [projectId, id, currentConfig, refetch]);

  const handleDelete = useCallback(async () => {
    if (!projectId || !id) return;
    setDeleting(true);
    try {
      await policyService.delete(projectId, id);
      toast.success("Policy deleted");
      navigate("/policies");
    } catch {
      toast.error("Failed to delete policy");
    } finally {
      setDeleting(false);
    }
  }, [projectId, id, navigate]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!policy) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        Policy not found.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate("/policies")}
      >
        <ChevronLeft className="mr-1 h-4 w-4" />
        Back to Policies
      </Button>

      <div className="space-y-2">
        <h1 className="text-2xl font-bold">{policy.name}</h1>
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="outline">{categoryLabel(policy.category)}</Badge>
          <Select
            value={policy.severity_default}
            onValueChange={(v) => handleSeverityChange(v as SeverityLevel)}
          >
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {severities.map((s) => (
                <SelectItem key={s} value={s}>
                  <Badge variant={severityBadgeVariant(s)}>{s}</Badge>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex items-center gap-2">
            <Switch
              checked={policy.is_active}
              onCheckedChange={handleToggle}
            />
            <span className="text-sm text-muted-foreground">
              {policy.is_active ? "Active" : "Inactive"}
            </span>
          </div>
          {policy.policy_template_id && (
            <Badge variant="secondary">From Template</Badge>
          )}
        </div>
        {policy.description && (
          <p className="text-muted-foreground">{policy.description}</p>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Textarea
                value={currentConfig}
                onChange={(e) => setConfigText(e.target.value)}
                className="min-h-[200px] font-mono text-sm"
                placeholder='{"key": "value"}'
              />
              <Button
                onClick={handleSaveConfig}
                disabled={savingConfig}
                size="sm"
              >
                {savingConfig ? "Saving..." : "Save Configuration"}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Violation History</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>File</TableHead>
                    <TableHead>Line</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Message</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell
                      colSpan={5}
                      className="text-center text-muted-foreground"
                    >
                      Violation history will appear here after scans are run.
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {policy.violation_count}
              </div>
              <p className="text-sm text-muted-foreground">
                Total violations found
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Policy Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created</span>
                <span>{formatDate(policy.created_at)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Updated</span>
                <span>{formatDate(policy.updated_at)}</span>
              </div>
            </CardContent>
          </Card>

          <Card className="border-destructive">
            <CardHeader>
              <CardTitle className="text-base text-destructive">
                Danger Zone
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setDeleteOpen(true)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete Policy
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Policy</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete "{policy.name}"? This action cannot
            be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
