import { useState, useCallback } from "react";
import { useProject } from "@/contexts/ProjectContext";
import { useApi } from "@/hooks/useApi";
import { knowledgeService } from "@/services/knowledgeService";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import PatternCard from "@/components/intelligence/PatternCard";
import PatternEvidenceDialog from "@/components/intelligence/PatternEvidenceDialog";
import ConventionTable from "@/components/intelligence/ConventionTable";
import ArchitectureDiagram from "@/components/intelligence/ArchitectureDiagram";
import SimilarCodeSearch from "@/components/intelligence/SimilarCodeSearch";
import { Brain, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function CodebaseIntelligence() {
  const { currentProject } = useProject();
  const projectId = currentProject?.id;

  const {
    data: patternsData,
    isLoading: patternsLoading,
    refetch: refetchPatterns,
  } = useApi(
    () =>
      projectId
        ? knowledgeService.listPatterns(projectId)
        : Promise.resolve(null),
    [projectId],
  );

  const {
    data: conventionsData,
    isLoading: conventionsLoading,
    refetch: refetchConventions,
  } = useApi(
    () =>
      projectId
        ? knowledgeService.listConventions(projectId)
        : Promise.resolve(null),
    [projectId],
  );

  const {
    data: architectureData,
    isLoading: architectureLoading,
    refetch: refetchArchitecture,
  } = useApi(
    () =>
      projectId
        ? knowledgeService.getArchitecture(projectId)
        : Promise.resolve(null),
    [projectId],
  );

  const [learningRunning, setLearningRunning] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [selectedPatternId, setSelectedPatternId] = useState<string | null>(
    null,
  );

  const handleViewEvidence = useCallback((patternId: string) => {
    setSelectedPatternId(patternId);
    setEvidenceOpen(true);
  }, []);

  const handleRunLearning = useCallback(async () => {
    if (!projectId) return;
    setLearningRunning(true);
    try {
      await knowledgeService.triggerLearning(projectId);
      toast.success("Convention learning started — results will appear once the background task completes.");
      // Delay refetch to give the Celery task time to run
      setTimeout(() => {
        refetchPatterns();
        refetchConventions();
        refetchArchitecture();
      }, 5000);
    } catch {
      toast.error("Failed to start convention learning");
    } finally {
      setLearningRunning(false);
    }
  }, [projectId, refetchPatterns, refetchConventions, refetchArchitecture]);

  if (!currentProject) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="text-center">
          <Brain className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h2 className="text-xl font-semibold">Codebase Intelligence</h2>
          <p className="mt-2 text-muted-foreground">
            Select a project to explore its codebase intelligence.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Codebase Intelligence</h1>
        <Button
          onClick={handleRunLearning}
          disabled={learningRunning}
          size="sm"
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${learningRunning ? "animate-spin" : ""}`}
          />
          {learningRunning ? "Learning..." : "Run Learning"}
        </Button>
      </div>

      <Tabs defaultValue="patterns">
        <TabsList>
          <TabsTrigger value="patterns">Patterns</TabsTrigger>
          <TabsTrigger value="conventions">Conventions</TabsTrigger>
          <TabsTrigger value="architecture">Architecture</TabsTrigger>
          <TabsTrigger value="similar">Similar Code</TabsTrigger>
        </TabsList>

        <TabsContent value="patterns" className="mt-4">
          {patternsLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-48" />
              ))}
            </div>
          ) : !patternsData?.patterns?.length ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No patterns discovered yet. Run indexing and learning to discover
              codebase patterns.
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {patternsData.patterns.map((p) => (
                <PatternCard
                  key={p.name}
                  pattern={p}
                  onViewEvidence={handleViewEvidence}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="conventions" className="mt-4">
          <ConventionTable
            conventions={conventionsData?.conventions ?? []}
            isLoading={conventionsLoading}
          />
        </TabsContent>

        <TabsContent value="architecture" className="mt-4">
          <ArchitectureDiagram
            architecture={architectureData ?? null}
            isLoading={architectureLoading}
          />
        </TabsContent>

        <TabsContent value="similar" className="mt-4">
          <SimilarCodeSearch projectId={projectId!} />
        </TabsContent>
      </Tabs>

      <PatternEvidenceDialog
        open={evidenceOpen}
        onOpenChange={setEvidenceOpen}
        projectId={projectId!}
        patternId={selectedPatternId}
      />
    </div>
  );
}
