import { useState, useMemo, useCallback } from "react";
import { useProject } from "@/contexts/ProjectContext";
import { useApi } from "@/hooks/useApi";
import { policyService } from "@/services/policyService";
import type { PolicyTemplateResponse } from "@/types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import PolicyCard from "@/components/policies/PolicyCard";
import PolicyTemplateCard from "@/components/policies/PolicyTemplateCard";
import CreatePolicyDialog from "@/components/policies/CreatePolicyDialog";
import ActivateTemplateDialog from "@/components/policies/ActivateTemplateDialog";
import { toast } from "sonner";
import { Plus, Shield } from "lucide-react";

export default function Policies() {
  const { currentProject } = useProject();
  const projectId = currentProject?.id;

  const {
    data: policies,
    isLoading: policiesLoading,
    refetch: refetchPolicies,
  } = useApi(
    () => (projectId ? policyService.list(projectId) : Promise.resolve([])),
    [projectId],
  );

  const { data: templates, isLoading: templatesLoading } = useApi(
    () => policyService.listBuiltin(),
    [],
  );

  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [activateTemplate, setActivateTemplate] =
    useState<PolicyTemplateResponse | null>(null);

  const filteredPolicies = useMemo(() => {
    if (!policies) return [];
    if (!search) return policies;
    const lower = search.toLowerCase();
    return policies.filter(
      (p) =>
        p.name.toLowerCase().includes(lower) ||
        p.category.toLowerCase().includes(lower),
    );
  }, [policies, search]);

  const activatedTemplateIds = useMemo(
    () => new Set(policies?.map((p) => p.policy_template_id).filter(Boolean)),
    [policies],
  );

  const handleToggle = useCallback(
    async (id: string, isActive: boolean) => {
      if (!projectId) return;
      try {
        await policyService.update(projectId, id, { is_active: isActive });
        refetchPolicies();
      } catch {
        toast.error("Failed to update policy");
      }
    },
    [projectId, refetchPolicies],
  );

  if (!currentProject) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="text-center">
          <Shield className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h2 className="text-xl font-semibold">No Project Selected</h2>
          <p className="mt-2 text-muted-foreground">
            Select or create a project to manage policies.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Policies</h1>

      <Tabs defaultValue="active">
        <TabsList>
          <TabsTrigger value="active">Active Policies</TabsTrigger>
          <TabsTrigger value="templates">Policy Templates</TabsTrigger>
        </TabsList>

        <TabsContent value="active" className="mt-4 space-y-4">
          <div className="flex items-center gap-4">
            <Input
              placeholder="Search policies..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Policy
            </Button>
          </div>

          {policiesLoading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-48" />
              ))}
            </div>
          ) : filteredPolicies.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              {search
                ? "No policies match your search."
                : "No policies configured. Activate a template or create a custom policy."}
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {filteredPolicies.map((p) => (
                <PolicyCard key={p.id} policy={p} onToggle={handleToggle} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="templates" className="mt-4">
          {templatesLoading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-48" />
              ))}
            </div>
          ) : !templates || templates.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              No policy templates available.
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {templates.map((t) => (
                <PolicyTemplateCard
                  key={t.id}
                  template={t}
                  onActivate={setActivateTemplate}
                  isActivated={activatedTemplateIds.has(t.id)}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      <CreatePolicyDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        projectId={projectId!}
        onCreated={refetchPolicies}
      />
      <ActivateTemplateDialog
        open={!!activateTemplate}
        onOpenChange={(open) => !open && setActivateTemplate(null)}
        template={activateTemplate}
        projectId={projectId!}
        onActivated={refetchPolicies}
      />
    </div>
  );
}
