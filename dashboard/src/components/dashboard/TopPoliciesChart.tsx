import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";

interface DataPoint {
  name: string;
  violations: number;
}

interface Props {
  data: DataPoint[];
  isLoading?: boolean;
}

export default function TopPoliciesChart({ data, isLoading }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Top Violated Policies</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-[250px] w-full" />
        ) : data.length === 0 ? (
          <div className="flex h-[250px] items-center justify-center text-sm text-muted-foreground">
            No policy violations recorded yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis
                dataKey="name"
                type="category"
                width={120}
                tick={{ fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                  color: "var(--foreground)",
                }}
              />
              <Bar
                dataKey="violations"
                fill="var(--chart-1)"
                radius={[0, 4, 4, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
