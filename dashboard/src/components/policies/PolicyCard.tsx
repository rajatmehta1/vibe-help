import { useNavigate } from "react-router-dom";
import type { PolicyResponse } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { categoryLabel, severityBadgeVariant } from "@/lib/formatters";

interface Props {
  policy: PolicyResponse;
  onToggle: (id: string, isActive: boolean) => void;
}

export default function PolicyCard({ policy, onToggle }: Props) {
  const navigate = useNavigate();

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{categoryLabel(policy.category)}</Badge>
            <Badge variant={severityBadgeVariant(policy.severity_default)}>
              {policy.severity_default}
            </Badge>
          </div>
          <Switch
            checked={policy.is_active}
            onCheckedChange={(checked) => onToggle(policy.id, checked)}
          />
        </div>
        <button
          className="mt-2 text-left text-base font-semibold hover:underline"
          onClick={() => navigate(`/policies/${policy.id}`)}
        >
          {policy.name}
        </button>
      </CardHeader>
      <CardContent className="flex-1">
        <p className="line-clamp-2 text-sm text-muted-foreground">
          {policy.description ?? "No description"}
        </p>
        {policy.policy_template_id && (
          <Badge variant="secondary" className="mt-3 text-xs">
            From Template
          </Badge>
        )}
      </CardContent>
    </Card>
  );
}
