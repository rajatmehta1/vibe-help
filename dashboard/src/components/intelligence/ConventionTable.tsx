import type { ConventionItem } from "@/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface Props {
  conventions: ConventionItem[];
  isLoading: boolean;
}

export default function ConventionTable({ conventions, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12" />
        ))}
      </div>
    );
  }

  if (conventions.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No conventions discovered. Run indexing and convention learning.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Category</TableHead>
          <TableHead>Description</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {conventions.map((c) => (
          <TableRow key={c.id}>
            <TableCell className="font-medium">{c.name}</TableCell>
            <TableCell>
              <Badge variant="outline">{c.category}</Badge>
            </TableCell>
            <TableCell className="text-muted-foreground">
              {c.description}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
