import { useState, useEffect, type FormEvent } from "react";
import type { PolicyTemplateResponse, SeverityLevel } from "@/types";
import { policyService } from "@/services/policyService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

const severities: SeverityLevel[] = ["error", "warning", "info"];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  template: PolicyTemplateResponse | null;
  projectId: string;
  onActivated: () => void;
}

export default function ActivateTemplateDialog({
  open,
  onOpenChange,
  template,
  projectId,
  onActivated,
}: Props) {
  const [name, setName] = useState("");
  const [severity, setSeverity] = useState<SeverityLevel>("warning");
  const [config, setConfig] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (template) {
      setName(template.name);
      setSeverity(template.default_severity);
      setConfig(
        template.default_configuration
          ? JSON.stringify(template.default_configuration, null, 2)
          : "",
      );
    }
  }, [template]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!template) return;
    setIsLoading(true);
    try {
      let configuration: Record<string, unknown> | undefined;
      if (config.trim()) {
        configuration = JSON.parse(config);
      }
      await policyService.create(projectId, {
        policy_template_id: template.id,
        name,
        category: template.category,
        severity_default: severity,
        description: template.description ?? undefined,
        configuration,
      });
      toast.success("Policy activated from template");
      onActivated();
      onOpenChange(false);
    } catch (err) {
      if (err instanceof SyntaxError) {
        toast.error("Invalid JSON in configuration");
      } else {
        toast.error("Failed to activate template");
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Activate Template: {template?.name}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="tmpl-name">Policy Name</Label>
            <Input
              id="tmpl-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label>Severity</Label>
            <Select
              value={severity}
              onValueChange={(v) => setSeverity(v as SeverityLevel)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {severities.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="tmpl-config">Configuration (JSON)</Label>
            <Textarea
              id="tmpl-config"
              value={config}
              onChange={(e) => setConfig(e.target.value)}
              className="font-mono text-sm"
              rows={6}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? "Activating..." : "Activate"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
