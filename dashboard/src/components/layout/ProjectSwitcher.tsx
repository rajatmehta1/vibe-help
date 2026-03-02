import { useState } from "react";
import { useProject } from "@/contexts/ProjectContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { ChevronsUpDown, FolderPlus, Check } from "lucide-react";
import CreateProjectDialog from "./CreateProjectDialog";

export default function ProjectSwitcher() {
  const { projects, currentProject, selectProject } = useProject();
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            className="w-full justify-between text-sidebar-foreground hover:bg-sidebar-accent"
          >
            <span className="truncate text-sm font-medium">
              {currentProject?.name ?? "Select Project"}
            </span>
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56">
          {projects.map((p) => (
            <DropdownMenuItem
              key={p.id}
              onClick={() => selectProject(p)}
              className="flex items-center justify-between"
            >
              <span className="truncate">{p.name}</span>
              {currentProject?.id === p.id && (
                <Check className="ml-2 h-4 w-4" />
              )}
            </DropdownMenuItem>
          ))}
          {projects.length > 0 && <DropdownMenuSeparator />}
          <DropdownMenuItem onClick={() => setDialogOpen(true)}>
            <FolderPlus className="mr-2 h-4 w-4" />
            Create New Project
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <CreateProjectDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </>
  );
}
