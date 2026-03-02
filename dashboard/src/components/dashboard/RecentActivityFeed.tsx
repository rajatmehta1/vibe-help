import type { AuditLogResponse } from "@/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatRelativeTime } from "@/lib/formatters";
import {
  AlertTriangle,
  FileSearch,
  Shield,
  Database,
  Activity,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface Props {
  activities: AuditLogResponse[];
  isLoading?: boolean;
}

const actionIcons: Record<string, LucideIcon> = {
  code_detected: AlertTriangle,
  scan_started: FileSearch,
  scan_completed: FileSearch,
  policy_created: Shield,
  policy_updated: Shield,
  index_started: Database,
  index_completed: Database,
};

function actionDescription(action: string): string {
  return action
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export default function RecentActivityFeed({ activities, isLoading }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-8 w-8 rounded-full" />
                <div className="flex-1 space-y-1">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
            ))}
          </div>
        ) : activities.length === 0 ? (
          <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
            No recent activity.
          </div>
        ) : (
          <ScrollArea className="h-[300px]">
            <div className="space-y-3">
              {activities.map((a) => {
                const Icon = actionIcons[a.action] ?? Activity;
                return (
                  <div key={a.id} className="flex items-start gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm">{actionDescription(a.action)}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatRelativeTime(a.created_at)}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
