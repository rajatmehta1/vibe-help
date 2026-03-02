import { useState } from "react";
import EmptyState from "./EmptyState";
import CreateProjectDialog from "@/components/layout/CreateProjectDialog";
import { Button } from "@/components/ui/button";
import { FolderOpen } from "lucide-react";

export default function NoProjectSelected() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <EmptyState
        icon={FolderOpen}
        title="No Project Selected"
        description="Create or select a project to get started."
        action={
          <Button onClick={() => setOpen(true)}>Create Project</Button>
        }
      />
      <CreateProjectDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
