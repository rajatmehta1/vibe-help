import { useApi } from "@/hooks/useApi";
import { knowledgeService } from "@/services/knowledgeService";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  patternId: string | null;
}

export default function PatternEvidenceDialog({
  open,
  onOpenChange,
  projectId,
  patternId,
}: Props) {
  const { data, isLoading } = useApi(
    () =>
      patternId
        ? knowledgeService.getPatternEvidence(projectId, patternId)
        : Promise.resolve(null),
    [projectId, patternId],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Pattern Evidence</DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        ) : !data || data.evidence.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No evidence found for this pattern.
          </p>
        ) : (
          <ScrollArea className="max-h-[400px]">
            <div className="space-y-3">
              {data.evidence.map((item, i) => {
                const evidence = item as Record<string, unknown>;
                return (
                  <div
                    key={i}
                    className="rounded-md border bg-muted/50 p-3"
                  >
                    {"file_path" in evidence && evidence["file_path"] ? (
                      <p className="mb-1 text-xs font-medium text-muted-foreground">
                        {String(evidence["file_path"])}
                      </p>
                    ) : null}
                    {"code_snippet" in evidence && evidence["code_snippet"] ? (
                      <pre className="overflow-x-auto text-xs">
                        <code>{String(evidence["code_snippet"])}</code>
                      </pre>
                    ) : (
                      <pre className="overflow-x-auto text-xs">
                        <code>{JSON.stringify(evidence, null, 2)}</code>
                      </pre>
                    )}
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}
