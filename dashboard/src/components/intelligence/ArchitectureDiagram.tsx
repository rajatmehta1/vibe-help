import type { ArchitectureResponse } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ArrowRight } from "lucide-react";

interface Props {
  architecture: ArchitectureResponse | null;
  isLoading: boolean;
}

export default function ArchitectureDiagram({
  architecture,
  isLoading,
}: Props) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }

  if (!architecture || architecture.layers.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        Index your codebase to discover its architecture.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        {architecture.layers.map((layer, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{layer.name}</CardTitle>
              {layer.description && (
                <p className="text-sm text-muted-foreground">
                  {layer.description}
                </p>
              )}
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {layer.modules.map((mod) => (
                  <Badge key={mod} variant="secondary">
                    {mod}
                  </Badge>
                ))}
                {layer.modules.length === 0 && (
                  <span className="text-sm text-muted-foreground">
                    {layer.module_count} modules
                  </span>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {architecture.cross_layer_relationships.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Cross-Layer Relationships
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>From</TableHead>
                  <TableHead></TableHead>
                  <TableHead>To</TableHead>
                  <TableHead>Count</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {architecture.cross_layer_relationships.map((rel, i) => (
                  <TableRow key={i}>
                    <TableCell>{rel.from_layer}</TableCell>
                    <TableCell>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    </TableCell>
                    <TableCell>{rel.to_layer}</TableCell>
                    <TableCell>{rel.count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
