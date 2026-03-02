import type { PatternItem } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

interface Props {
  pattern: PatternItem;
  onViewEvidence: (patternId: string) => void;
}

export default function PatternCard({ pattern, onViewEvidence }: Props) {
  const confidencePct = Math.round(pattern.confidence * 100);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <h3 className="font-semibold">{pattern.name}</h3>
          <Badge variant="outline">{pattern.category}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">{pattern.description}</p>
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Confidence</span>
            <span
              className={
                confidencePct >= 80
                  ? "text-green-500"
                  : confidencePct >= 50
                    ? "text-yellow-500"
                    : "text-red-500"
              }
            >
              {confidencePct}%
            </span>
          </div>
          <Progress value={confidencePct} className="h-2" />
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onViewEvidence(pattern.id)}
        >
          View Evidence
        </Button>
      </CardContent>
    </Card>
  );
}
