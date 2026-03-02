import { useState, useCallback } from "react";
import type { SimilarCodeResult } from "@/types";
import { knowledgeService } from "@/services/knowledgeService";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Search } from "lucide-react";

const languages = [
  "python",
  "typescript",
  "javascript",
  "go",
  "rust",
  "java",
];

interface Props {
  projectId: string;
}

export default function SimilarCodeSearch({ projectId }: Props) {
  const [code, setCode] = useState("");
  const [language, setLanguage] = useState("python");
  const [results, setResults] = useState<SimilarCodeResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = useCallback(async () => {
    if (!code.trim()) return;
    setIsLoading(true);
    setSearched(true);
    try {
      const res = await knowledgeService.findSimilar(projectId, {
        code,
        language,
        limit: 10,
      });
      setResults(res.results);
    } catch {
      toast.error("Failed to search for similar code");
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, [projectId, code, language]);

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Code Snippet</Label>
        <Textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="min-h-[150px] font-mono text-sm"
          placeholder="Paste code here to find similar code in your codebase..."
        />
      </div>
      <div className="flex items-end gap-4">
        <div className="space-y-2">
          <Label>Language</Label>
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {languages.map((l) => (
                <SelectItem key={l} value={l}>
                  {l.charAt(0).toUpperCase() + l.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={handleSearch} disabled={isLoading || !code.trim()}>
          <Search className="mr-2 h-4 w-4" />
          {isLoading ? "Searching..." : "Find Similar"}
        </Button>
      </div>

      {searched && (
        <div className="space-y-3">
          {results.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {isLoading
                ? "Searching..."
                : "No similar code found. Try indexing your codebase first."}
            </p>
          ) : (
            results.map((r, i) => (
              <Card key={i}>
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">{r.code_unit_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {r.file_path}
                      </p>
                    </div>
                    <span className="text-sm font-medium">
                      {Math.round(r.similarity_score * 100)}%
                    </span>
                  </div>
                  <Progress
                    value={r.similarity_score * 100}
                    className="mt-2 h-1.5"
                  />
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}
