import { useState, useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/PageHeader";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ClipboardList,
  ChevronDown,
  ChevronRight,
  Wifi,
  WifiOff,
  Code2,
  GitCommit,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { useAuditLogs, AuditEntry } from "@/hooks/useAuditLogs";
import { useStrategies } from "@/hooks/useStrategies";
import { cn } from "@/lib/utils";

const EVENT_LABELS: Record<string, { label: string; color: string }> = {
  api_call:        { label: "API Call",         color: "bg-primary/15 text-primary" },
  strategy_change: { label: "Strategy Change",  color: "bg-violet-500/15 text-violet-400" },
  contact_change:  { label: "Contact Change",   color: "bg-amber-500/15 text-amber-400" },
  step_change:     { label: "Step Change",      color: "bg-sky-500/15 text-sky-400" },
};

const SERVICE_COLORS: Record<string, string> = {
  serpapi:   "bg-emerald-500/15 text-emerald-400",
  apollo:    "bg-blue-500/15 text-blue-400",
  instantly: "bg-orange-500/15 text-orange-400",
  openai:    "bg-purple-500/15 text-purple-400",
  internal:  "bg-muted text-muted-foreground",
};

function fmtTs(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hour12: false,
  });
}

function StatusBadge({ status }: { status: number | null }) {
  if (status == null) return <span className="text-muted-foreground">—</span>;
  const ok = status >= 200 && status < 300;
  return (
    <span className={cn("font-mono text-xs", ok ? "text-primary" : "text-destructive")}>
      {status}
    </span>
  );
}

function ExpandedRow({ entry }: { entry: AuditEntry }) {
  const hasCurl = Boolean(entry.curl_command);
  const hasChange = entry.change_field != null;
  const hasResponse = entry.response_summary && Object.keys(entry.response_summary).length > 0;

  if (!hasCurl && !hasChange && !hasResponse) {
    return (
      <div className="py-3 text-xs text-muted-foreground">No additional details.</div>
    );
  }

  return (
    <div className="space-y-3 py-2">
      {hasCurl && (
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            <Code2 className="h-3 w-3" /> cURL Replay
          </div>
          <pre className="overflow-x-auto rounded bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-green-300 whitespace-pre-wrap">
            {entry.curl_command}
          </pre>
        </div>
      )}

      {hasResponse && (
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            <Code2 className="h-3 w-3" /> Response Output
          </div>
          <pre className="overflow-x-auto rounded bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-sky-300 whitespace-pre-wrap">
            {JSON.stringify(entry.response_summary, null, 2)}
          </pre>
        </div>
      )}

      {hasChange && (
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            <GitCommit className="h-3 w-3" /> Change — <span className="text-foreground">{entry.change_field}</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Before</div>
              <pre className="overflow-x-auto rounded bg-black/40 p-2 font-mono text-[11px] text-rose-300 whitespace-pre-wrap">
                {JSON.stringify(entry.change_before, null, 2)}
              </pre>
            </div>
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">After</div>
              <pre className="overflow-x-auto rounded bg-black/40 p-2 font-mono text-[11px] text-emerald-300 whitespace-pre-wrap">
                {JSON.stringify(entry.change_after, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AuditRow({ entry }: { entry: AuditEntry }) {
  const [expanded, setExpanded] = useState(false);
  const eventMeta = EVENT_LABELS[entry.event_type] ?? { label: entry.event_type, color: "bg-muted text-muted-foreground" };
  const serviceColor = SERVICE_COLORS[entry.service ?? "internal"] ?? SERVICE_COLORS.internal;
  const hasDetails =
    Boolean(entry.curl_command) ||
    entry.change_field != null ||
    (entry.response_summary != null && Object.keys(entry.response_summary).length > 0);

  return (
    <>
      <tr
        className={cn(
          "border-b border-border/50 text-sm transition-colors",
          hasDetails && "cursor-pointer hover:bg-muted/30",
          expanded && "bg-muted/20",
        )}
        onClick={() => hasDetails && setExpanded((p) => !p)}
      >
        <td className="py-2 pr-3 font-mono text-[11px] text-muted-foreground whitespace-nowrap">
          {entry.occurred_at ? fmtTs(entry.occurred_at) : "—"}
        </td>
        <td className="py-2 pr-3">
          <span className={cn("rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wider font-medium", eventMeta.color)}>
            {eventMeta.label}
          </span>
        </td>
        <td className="py-2 pr-3">
          {entry.service && (
            <span className={cn("rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wider font-medium", serviceColor)}>
              {entry.service}
            </span>
          )}
        </td>
        <td className="py-2 pr-4 max-w-xs">
          <div className="truncate text-xs text-foreground/90">{entry.summary ?? "—"}</div>
          {entry.strategy_name && (
            <div className="truncate text-[11px] text-muted-foreground">{entry.strategy_name}</div>
          )}
        </td>
        <td className="py-2 pr-3">
          <StatusBadge status={entry.response_status} />
        </td>
        <td className="py-2 pr-3 font-mono text-xs text-muted-foreground whitespace-nowrap">
          {entry.latency_ms != null ? `${entry.latency_ms} ms` : "—"}
        </td>
        <td className="py-2 pr-3">
          {entry.is_live ? (
            <span className="inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-primary">
              <Wifi className="h-3 w-3" /> Live
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              <WifiOff className="h-3 w-3" /> Internal
            </span>
          )}
        </td>
        <td className="py-2 text-right">
          {hasDetails && (
            expanded
              ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
              : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border/50">
          <td colSpan={8} className="px-4 pb-3">
            <ExpandedRow entry={entry} />
          </td>
        </tr>
      )}
    </>
  );
}

const TIME_RANGES = [
  { label: "Last 24 h", hours: 24 },
  { label: "Last 7 days", hours: 24 * 7 },
  { label: "Last 30 days", hours: 24 * 30 },
  { label: "All time", hours: 0 },
];

function tsFromHours(hours: number): string | undefined {
  if (!hours) return undefined;
  return new Date(Date.now() - hours * 3_600_000).toISOString();
}

export function Audit() {
  const { data: strategiesData } = useStrategies();
  const [strategyId, setStrategyId] = useState<string>("");
  const [service, setService] = useState<string>("");
  const [eventType, setEventType] = useState<string>("");
  const [timeRange, setTimeRange] = useState<number>(24 * 7);
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;

  const fromTs = useMemo(() => tsFromHours(timeRange), [timeRange]);
  const { data, isLoading, isError, error, refetch, isFetching } = useAuditLogs({
    strategy_id: strategyId || undefined,
    service: service || undefined,
    event_type: eventType || undefined,
    from_ts: fromTs,
    limit: LIMIT,
    offset,
  });

  const logs = data?.logs ?? [];
  const total = data?.total ?? 0;

  return (
    <>
      <PageHeader
        eyebrow="Observability"
        title="Audit Log"
        subtitle="Every external API call and data change, with timestamps, HTTP details, and curl commands."
      />

      <Card className="mb-4 border-card-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Select value={strategyId} onValueChange={(v) => { setStrategyId(v === "_all" ? "" : v); setOffset(0); }}>
            <SelectTrigger className="h-8 w-48 text-xs">
              <SelectValue placeholder="All strategies" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">All strategies</SelectItem>
              {strategiesData?.map((s) => (
                <SelectItem key={s.id} value={s.id}>{s.product_name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={eventType} onValueChange={(v) => { setEventType(v === "_all" ? "" : v); setOffset(0); }}>
            <SelectTrigger className="h-8 w-44 text-xs">
              <SelectValue placeholder="All event types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">All event types</SelectItem>
              <SelectItem value="api_call">API Calls</SelectItem>
              <SelectItem value="strategy_change">Strategy Changes</SelectItem>
              <SelectItem value="contact_change">Contact Changes</SelectItem>
              <SelectItem value="step_change">Step Changes</SelectItem>
            </SelectContent>
          </Select>

          <Select value={service} onValueChange={(v) => { setService(v === "_all" ? "" : v); setOffset(0); }}>
            <SelectTrigger className="h-8 w-36 text-xs">
              <SelectValue placeholder="All services" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">All services</SelectItem>
              <SelectItem value="serpapi">SerpAPI</SelectItem>
              <SelectItem value="apollo">Apollo</SelectItem>
              <SelectItem value="instantly">Instantly</SelectItem>
              <SelectItem value="openai">OpenAI</SelectItem>
              <SelectItem value="internal">Internal</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={String(timeRange)}
            onValueChange={(v) => { setTimeRange(Number(v)); setOffset(0); }}
          >
            <SelectTrigger className="h-8 w-36 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIME_RANGES.map((r) => (
                <SelectItem key={r.hours} value={String(r.hours)}>{r.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button
            size="sm"
            variant="secondary"
            className="h-8 gap-1.5"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={cn("h-3 w-3", isFetching && "animate-spin")} />
            Refresh
          </Button>

          <div className="ml-auto text-xs text-muted-foreground">
            {total > 0 ? <>{total.toLocaleString()} total entries</> : null}
          </div>
        </div>
      </Card>

      <Card className="border-card-border bg-card">
        {isError ? (
          <div className="flex flex-col items-center gap-3 p-16 text-center">
            <AlertCircle className="h-8 w-8 text-destructive/40" />
            <div className="text-sm font-medium text-foreground/70">Could not load audit log</div>
            <div className="text-xs text-muted-foreground font-mono">{String((error as Error)?.message ?? error)}</div>
            <Button size="sm" variant="secondary" onClick={() => refetch()}>Retry</Button>
          </div>
        ) : isLoading ? (
          <div className="flex items-center justify-center gap-2 p-12 text-sm text-muted-foreground">
            <RefreshCw className="h-4 w-4 animate-spin" /> Loading audit log…
          </div>
        ) : logs.length === 0 ? (
          <div className="flex flex-col items-center gap-3 p-16 text-center">
            <ClipboardList className="h-8 w-8 text-muted-foreground/40" />
            <div className="text-sm font-medium text-foreground/70">No audit entries yet</div>
            <div className="max-w-xs text-xs text-muted-foreground">
              Entries appear here the first time you run a live API call (Discover leads,
              Market sizing, Launch outreach) or edit any strategy, contact, or sequence step.
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-4 py-2.5 text-[10px] uppercase tracking-widest text-muted-foreground">Timestamp</th>
                  <th className="pr-3 py-2.5 text-[10px] uppercase tracking-widest text-muted-foreground">Event</th>
                  <th className="pr-3 py-2.5 text-[10px] uppercase tracking-widest text-muted-foreground">Service</th>
                  <th className="pr-4 py-2.5 text-[10px] uppercase tracking-widest text-muted-foreground">Summary</th>
                  <th className="pr-3 py-2.5 text-[10px] uppercase tracking-widest text-muted-foreground">Status</th>
                  <th className="pr-3 py-2.5 text-[10px] uppercase tracking-widest text-muted-foreground">Latency</th>
                  <th className="pr-3 py-2.5 text-[10px] uppercase tracking-widest text-muted-foreground">Source</th>
                  <th className="py-2.5 pr-4" />
                </tr>
              </thead>
              <tbody>
                {logs.map((entry) => (
                  <AuditRow key={entry.id} entry={entry} />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > LIMIT && (
          <div className="flex items-center justify-between border-t border-border px-4 py-3">
            <div className="text-xs text-muted-foreground">
              Showing {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="secondary"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - LIMIT))}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={offset + LIMIT >= total}
                onClick={() => setOffset(offset + LIMIT)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}
