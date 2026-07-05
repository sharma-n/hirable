"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiGetAnalytics, type Analytics } from "@/lib/api";

const EMPTY_ANALYTICS: Analytics = {
  funnel: [],
  response_rate: 0,
  median_time_to_first_response_days: null,
  applications_over_time: [],
  status_counts: { by_stage: {}, active: 0, stale: 0, rejected: 0, offers: 0 },
  offer_rate: 0,
  cv_version_performance: [],
  by_company_type: [],
  by_location: [],
};

// Ordinal blue ramp (light -> dark), one step per funnel stage — see the
// dataviz skill's ordinal-ramp guidance for ordered categories like funnel
// stages. Six steps covers SPEC's FUNNEL_STAGES exactly.
const FUNNEL_RAMP_LIGHT = ["#86b6ef", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#184f95"];
const FUNNEL_RAMP_DARK = ["#9ec5f4", "#86b6ef", "#5598e7", "#3987e5", "#256abf", "#1c5cab"];

function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card size="sm">
      <CardContent className="space-y-1">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold">{value}</p>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}

function ChartTooltip({
  active,
  payload,
  label,
  formatter,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
  formatter?: (value: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const value = payload[0].value;
  return (
    <div className="rounded-md border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-sm">
      <p className="font-medium">{label}</p>
      <p className="text-muted-foreground">{formatter ? formatter(value) : value}</p>
    </div>
  );
}

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<Analytics | "loading">("loading");
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const seriesColor = isDark ? "#3987e5" : "#2a78d6";
  const gridColor = isDark ? "#2c2c2a" : "#e1e0d9";
  const axisColor = isDark ? "#c3c2b7" : "#898781";
  const funnelRamp = isDark ? FUNNEL_RAMP_DARK : FUNNEL_RAMP_LIGHT;

  useEffect(() => {
    apiGetAnalytics()
      .then(setAnalytics)
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : "Failed to load analytics");
        setAnalytics(EMPTY_ANALYTICS);
      });
  }, []);

  if (analytics === "loading") {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const totalApplications = Object.values(analytics.status_counts.by_stage).reduce(
    (sum, n) => sum + n,
    0,
  );

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-8">
      <div>
        <h1 className="text-xl font-bold">Analytics</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          How your job search is performing, end to end.
        </p>
      </div>

      {totalApplications === 0 ? (
        <p className="py-16 text-center text-sm text-muted-foreground">
          Nothing to show yet — submit an application to start seeing analytics.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <StatTile label="Response rate" value={pct(analytics.response_rate)} />
            <StatTile label="Offer rate" value={pct(analytics.offer_rate)} />
            <StatTile
              label="Time to first response"
              value={
                analytics.median_time_to_first_response_days === null
                  ? "—"
                  : `${Math.round(analytics.median_time_to_first_response_days)}d`
              }
              sub="median"
            />
            <StatTile label="Active" value={String(analytics.status_counts.active)} />
            <StatTile label="Stale" value={String(analytics.status_counts.stale)} />
            <StatTile label="Rejected" value={String(analytics.status_counts.rejected)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Funnel</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    data={analytics.funnel}
                    layout="vertical"
                    margin={{ left: 8, right: 24, top: 4, bottom: 4 }}
                  >
                    <CartesianGrid horizontal={false} stroke={gridColor} />
                    <XAxis type="number" allowDecimals={false} stroke={axisColor} fontSize={12} />
                    <YAxis
                      type="category"
                      dataKey="stage"
                      width={110}
                      stroke={axisColor}
                      fontSize={12}
                      tickLine={false}
                    />
                    <Tooltip
                      content={
                        <ChartTooltip
                          formatter={(v) => {
                            const row = analytics.funnel.find((f) => f.count === v);
                            return row ? `${v} (${pct(row.pct_of_applied)} of applied)` : String(v);
                          }}
                        />
                      }
                      cursor={{ fill: isDark ? "#ffffff0d" : "#0000000d" }}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={24}>
                      {analytics.funnel.map((entry, i) => (
                        <Cell key={entry.stage} fill={funnelRamp[i % funnelRamp.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Applications over time</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart
                    data={analytics.applications_over_time}
                    margin={{ left: 0, right: 16, top: 4, bottom: 4 }}
                  >
                    <CartesianGrid vertical={false} stroke={gridColor} />
                    <XAxis dataKey="month" stroke={axisColor} fontSize={12} tickLine={false} />
                    <YAxis
                      allowDecimals={false}
                      stroke={axisColor}
                      fontSize={12}
                      tickLine={false}
                      width={28}
                    />
                    <Tooltip content={<ChartTooltip />} cursor={{ stroke: gridColor }} />
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke={seriesColor}
                      strokeWidth={2}
                      dot={{ r: 4, fill: seriesColor, stroke: "transparent" }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>By company type</CardTitle>
              </CardHeader>
              <CardContent>
                <BreakdownTable rows={analytics.by_company_type} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>By location</CardTitle>
              </CardHeader>
              <CardContent>
                <BreakdownTable rows={analytics.by_location} />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>CV version performance</CardTitle>
              </CardHeader>
              <CardContent>
                {analytics.cv_version_performance.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No submitted applications with a finalized CV yet.
                  </p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Version</TableHead>
                        <TableHead>Submitted</TableHead>
                        <TableHead>Responded</TableHead>
                        <TableHead>Response rate</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {analytics.cv_version_performance.map((row) => (
                        <TableRow key={row.version}>
                          <TableCell className="font-medium">v{row.version}</TableCell>
                          <TableCell>{row.submitted_count}</TableCell>
                          <TableCell>{row.response_count}</TableCell>
                          <TableCell>{pct(row.response_rate)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Status breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Stage</TableHead>
                      <TableHead>Count</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Object.entries(analytics.status_counts.by_stage)
                      .filter(([, count]) => count > 0)
                      .map(([stage, count]) => (
                        <TableRow key={stage}>
                          <TableCell className="font-medium">{stage}</TableCell>
                          <TableCell>{count}</TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function BreakdownTable({
  rows,
}: {
  rows: { key: string; count: number; response_count: number; response_rate: number }[];
}) {
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No submitted applications yet.</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Group</TableHead>
          <TableHead>Submitted</TableHead>
          <TableHead>Response rate</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.key}>
            <TableCell className={row.key === "Unknown" ? "text-muted-foreground" : "font-medium"}>
              {row.key}
            </TableCell>
            <TableCell>{row.count}</TableCell>
            <TableCell>{pct(row.response_rate)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
