import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useProject } from "@/contexts/ProjectContext";
import { projectService } from "@/services/projectService";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";

export default function DangerZone() {
  const { currentProject, refreshProjects } = useProject();
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const [confirmName, setConfirmName] = useState("");
  const [deleting, setDeleting] = useState(false);

  const handleDelete = useCallback(async () => {
    if (!currentProject) return;
    setDeleting(true);
    try {
      await projectService.delete(currentProject.id);
      toast.success("Project deleted");
      refreshProjects();
      navigate("/");
    } catch {
      toast.error("Failed to delete project");
    } finally {
      setDeleting(false);
      setOpen(false);
    }
  }, [currentProject, refreshProjects, navigate]);

  if (!currentProject) return null;

  return (
    <>
      <Card className="border-destructive">
        <CardHeader>
          <CardTitle className="text-base text-destructive">
            Danger Zone
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-sm text-muted-foreground">
            Deleting a project will permanently remove all its policies, scans,
            and indexed data.
          </p>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setOpen(true)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete Project
          </Button>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Project</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This action cannot be undone. Type{" "}
            <strong>{currentProject.name}</strong> to confirm.
          </p>
          <Input
            value={confirmName}
            onChange={(e) => setConfirmName(e.target.value)}
            placeholder="Project name"
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setOpen(false);
                setConfirmName("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting || confirmName !== currentProject.name}
            >
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
