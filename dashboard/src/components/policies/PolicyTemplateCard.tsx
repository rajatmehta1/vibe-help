import type { PolicyTemplateResponse } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { categoryLabel, severityBadgeVariant } from "@/lib/formatters";

interface Props {
  template: PolicyTemplateResponse;
  onActivate: (template: PolicyTemplateResponse) => void;
  isActivated: boolean;
}

export default function PolicyTemplateCard({
  template,
  onActivate,
  isActivated,
}: Props) {
  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{categoryLabel(template.category)}</Badge>
          <Badge variant={severityBadgeVariant(template.default_severity)}>
            {template.default_severity}
          </Badge>
          {template.version && (
            <Badge variant="secondary" className="text-xs">
              v{template.version}
            </Badge>
          )}
        </div>
        <h3 className="mt-2 text-base font-semibold">{template.name}</h3>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col justify-between gap-4">
        <p className="line-clamp-3 text-sm text-muted-foreground">
          {template.description ?? "No description"}
        </p>
        {isActivated ? (
          <Badge variant="secondary" className="w-fit">
            Active
          </Badge>
        ) : (
          <Button size="sm" onClick={() => onActivate(template)}>
            Activate
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
