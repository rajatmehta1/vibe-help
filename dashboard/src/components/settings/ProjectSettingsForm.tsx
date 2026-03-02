import { useState, useEffect, useCallback } from "react";
import { useProject } from "@/contexts/ProjectContext";
import { projectService } from "@/services/projectService";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

const languages = [
  "python",
  "typescript",
  "javascript",
  "go",
  "rust",
  "java",
  "csharp",
];

export default function ProjectSettingsForm() {
  const { currentProject, refreshProjects } = useProject();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [rootPath, setRootPath] = useState("");
  const [primaryLanguage, setPrimaryLanguage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (currentProject) {
      setName(currentProject.name);
      setDescription(currentProject.description ?? "");
      setRootPath(currentProject.root_path ?? "");
      setPrimaryLanguage(currentProject.primary_language ?? "");
    }
  }, [currentProject]);

  const handleSave = useCallback(async () => {
    if (!currentProject) return;
    setSaving(true);
    try {
      await projectService.update(currentProject.id, {
        name,
        description: description || undefined,
        root_path: rootPath || undefined,
        primary_language: primaryLanguage || undefined,
      });
      refreshProjects();
      toast.success("Project settings saved");
    } catch {
      toast.error("Failed to save project settings");
    } finally {
      setSaving(false);
    }
  }, [currentProject, name, description, rootPath, primaryLanguage, refreshProjects]);

  if (!currentProject) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Project Settings</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Project Name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label>Description</Label>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Project description..."
          />
        </div>
        <div className="space-y-2">
          <Label>Root Path</Label>
          <Input
            value={rootPath}
            onChange={(e) => setRootPath(e.target.value)}
            placeholder="/path/to/project"
          />
        </div>
        <div className="space-y-2">
          <Label>Primary Language</Label>
          <Select value={primaryLanguage} onValueChange={setPrimaryLanguage}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Select language" />
            </SelectTrigger>
            <SelectContent>
              {languages.map((l) => (
                <SelectItem key={l} value={l}>
                  {l.charAt(0).toUpperCase() + l.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={handleSave} disabled={saving || !name.trim()}>
          {saving ? "Saving..." : "Save Settings"}
        </Button>
      </CardContent>
    </Card>
  );
}
