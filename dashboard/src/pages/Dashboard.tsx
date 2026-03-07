import { useMemo } from "react";
import { useProject } from "@/contexts/ProjectContext";
import { useApi } from "@/hooks/useApi";
import { projectService } from "@/services/projectService";
import { policyService } from "@/services/policyService";
import { scanService } from "@/services/scanService";
import { categoryLabel, formatRelativeTime } from "@/lib/formatters";
import StatCard from "@/components/dashboard/StatCard";
import ViolationsOverTimeChart from "@/components/dashboard/ViolationsOverTimeChart";
import TopPoliciesChart from "@/components/dashboard/TopPoliciesChart";
import CategoryDonutChart from "@/components/dashboard/CategoryDonutChart";
import RecentActivityFeed from "@/components/dashboard/RecentActivityFeed";
import { Shield, ShieldCheck, AlertTriangle, Clock } from "lucide-react";
import type { AuditLogResponse } from "@/types";

export default function Dashboard() {
  const { currentProject } = useProject();
  const projectId = currentProject?.id;

  const { data: projectDetail, isLoading: projectLoading } = useApi(
    () => (projectId ? projectService.get(projectId) : Promise.resolve(null)),
    [projectId],
  );

  const { data: policies, isLoading: policiesLoading } = useApi(
    () => (projectId ? policyService.list(projectId) : Promise.resolve([])),
    [projectId],
  );

  const { data: stats, isLoading: statsLoading } = useApi(
    () => (projectId ? scanService.getStats(projectId) : Promise.resolve(null)),
    [projectId],
  );

  const isLoading = projectLoading || policiesLoading || statsLoading;

  const activePolicies = useMemo(
    () => policies?.filter((p) => p.is_active).length ?? 0,
    [policies],
  );

  const categoryData = useMemo(() => {
    if (!policies || policies.length === 0) return [];
    const counts: Record<string, number> = {};
    for (const p of policies) {
      counts[p.category] = (counts[p.category] ?? 0) + 1;
    }
    return Object.entries(counts).map(([category, count]) => ({
      category: categoryLabel(category as never),
      count,
    }));
  }, [policies]);

  if (!currentProject) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="text-center">
          <Shield className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h2 className="text-xl font-semibold">Welcome to ForgeLine</h2>
          <p className="mt-2 text-muted-foreground">
            Create or select a project to get started.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Policies"
          value={projectDetail?.policy_count ?? 0}
          description="Configured policies"
          icon={Shield}
          isLoading={isLoading}
        />
        <StatCard
          title="Active Policies"
          value={activePolicies}
          description="Currently enforced"
          icon={ShieldCheck}
          isLoading={isLoading}
        />
        <StatCard
          title="Total Violations"
          value={stats?.total_violations ?? 0}
          description="Across all completed scans"
          icon={AlertTriangle}
          isLoading={isLoading}
        />
        <StatCard
          title="Last Scan"
          value={
            projectDetail?.last_scan_at
              ? formatRelativeTime(projectDetail.last_scan_at)
              : "Never"
          }
          description={
            projectDetail?.last_indexed_at
              ? `Indexed ${formatRelativeTime(projectDetail.last_indexed_at)}`
              : "Not indexed yet"
          }
          icon={Clock}
          isLoading={isLoading}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ViolationsOverTimeChart data={stats?.scans_over_time ?? []} isLoading={isLoading} />
        <TopPoliciesChart data={stats?.top_policies ?? []} isLoading={isLoading} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <CategoryDonutChart data={categoryData} isLoading={isLoading} />
        <div className="lg:col-span-2">
          <RecentActivityFeed
            activities={(stats?.recent_activity ?? []) as AuditLogResponse[]}
            isLoading={isLoading}
          />
        </div>
      </div>
    </div>
  );
}
