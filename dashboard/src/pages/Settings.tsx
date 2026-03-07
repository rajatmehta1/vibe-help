import { useProject } from "@/contexts/ProjectContext";
import ProjectSettingsForm from "@/components/settings/ProjectSettingsForm";
import IndexingManager from "@/components/settings/IndexingManager";
import ScanManager from "@/components/settings/ScanManager";
import NotificationPrefs from "@/components/settings/NotificationPrefs";
import DangerZone from "@/components/settings/DangerZone";
import { Settings2 } from "lucide-react";

export default function Settings() {
  const { currentProject } = useProject();

  if (!currentProject) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="text-center">
          <Settings2 className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h2 className="text-xl font-semibold">Settings</h2>
          <p className="mt-2 text-muted-foreground">
            Select a project to manage its settings.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <ProjectSettingsForm />
          <IndexingManager />
          <ScanManager />
        </div>
        <div className="space-y-6">
          <NotificationPrefs />
          <DangerZone />
        </div>
      </div>
    </div>
  );
}
