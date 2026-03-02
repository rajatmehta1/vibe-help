import { useState, type FormEvent } from "react";
import type { PolicyCategory, SeverityLevel } from "@/types";
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
import { categoryLabel } from "@/lib/formatters";

const categories: PolicyCategory[] = [
  "security",
  "naming",
  "architecture",
  "error_handling",
  "dependencies",
  "performance",
  "documentation",
  "custom",
];

const severities: SeverityLevel[] = ["error", "warning", "info"];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  onCreated: () => void;
}

export default function CreatePolicyDialog({
  open,
  onOpenChange,
  projectId,
  onCreated,
}: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<PolicyCategory>("custom");
  const [severity, setSeverity] = useState<SeverityLevel>("warning");
  const [config, setConfig] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    try {
      let configuration: Record<string, unknown> | undefined;
      if (config.trim()) {
        configuration = JSON.parse(config);
      }
      await policyService.create(projectId, {
        name,
        description: description || undefined,
        category,
        severity_default: severity,
        configuration,
      });
      toast.success("Policy created");
      onCreated();
      onOpenChange(false);
      setName("");
      setDescription("");
      setConfig("");
    } catch (err) {
      if (err instanceof SyntaxError) {
        toast.error("Invalid JSON in configuration");
      } else {
        toast.error("Failed to create policy");
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Create Custom Policy</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="policy-name">Policy Name</Label>
            <Input
              id="policy-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="policy-desc">Description</Label>
            <Textarea
              id="policy-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Category</Label>
              <Select
                value={category}
                onValueChange={(v) => setCategory(v as PolicyCategory)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {categories.map((c) => (
                    <SelectItem key={c} value={c}>
                      {categoryLabel(c)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
          </div>
          <div className="space-y-2">
            <Label htmlFor="policy-config">Configuration (JSON)</Label>
            <Textarea
              id="policy-config"
              value={config}
              onChange={(e) => setConfig(e.target.value)}
              className="font-mono text-sm"
              rows={4}
              placeholder='{"key": "value"}'
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
              {isLoading ? "Creating..." : "Create Policy"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
