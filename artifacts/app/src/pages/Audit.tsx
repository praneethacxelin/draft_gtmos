import { useState, useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  Workflow,
  User,
  Cpu,
  Globe,
  Layers,
} from "lucide-react";
import {
  useAuditLogs,
  useAuditLogsByStrategy,
  AuditEntry,
  StrategyAuditGroup,
} from "@/hooks/useAuditLogs";
import { useStrategies } from "@/hooks/useStrategies";
import { cn } from "@/lib/utils";

/* ─── Constants ─── */

const EVENT_LABELS: Record<string, { label: string; color: string }> = {
  api_call:        { label: "API Call",         color: "bg-primary/15 text-primary" },
  strategy_change: { label: "Strategy Change",  color: "bg-violet-500/15 text-violet-400" },
  contact_change:  { label: "Contact Change",   color: "bg-amber-500/15 text-amber-400" },
  step_change:     { label: "Step Change",      color: "bg-sky-500/15 text-sky-400" },
  pipeline_stage:  { label: "Pipeline Stage",   color: "bg-emerald-500/15 text-emerald-400" },
};

const SERVICE_COLORS: Record<string, string> = {
  serpapi:       "bg-emerald-500/15 text-emerald-400",
  apollo:        "bg-blue-500/15 text-blue-400",
  instantly:     "bg-orange-500/15 text-orange-400",
  openai:        "bg-purple-500/15 text-purple-400",
  s1_strategy:   "bg-violet-500/15 text-violet-400",
  s2_signals:    "bg-cyan-500/15 text-cyan-400",
  s3_outreach:   "bg-rose-500/15 text-rose-400",
  internal:      "bg-muted text-muted-foreground",
};

const STAGE_META: Record<string, { label: string; icon: "user" | "ai" | "api" }> = {
  strategy_created: { label: "Strategy Created", icon: "user" },
  user_input:       { label: "User Input → Brief", icon: "user" },
  icp:              { label: "ICP Modeling", icon: "ai" },
  personas:         { label: "Persona Mapping", icon: "ai" },
  problems:         { label: "Problem Map", icon: "ai" },
  naics:            { label: "NAICS Segmentation", icon: "ai" },
  stakeholders:     { label: "Stakeholder Graph", icon: "ai" },
  use_cases:        { label: "Use Case Library", icon: "ai" },
  complete:         { label: "Pipeline Complete", icon: "ai" },
  market_sizing:    { label: "Market Sizing", icon: "api" },
  lead_search:      { label: "Lead Discovery", icon: "api" },
  signals:          { label: "Intent Signals", icon: "api" },
  scoring:          { label: "Lead Scoring", icon: "ai" },
  channel_plan:     { label: "Channel Plan", icon: "ai" },
  message_generation: { label: "Message Draft", icon: "ai" },
  launch:           { label: "Campaign Launch", icon: "api" },
};

/* ─── Helpers ─── */

function fmtTs(iso: string) {
  const dateStr = iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`;
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hour12: false,
  });
}

function SourceIcon({ type }: { type: "user" | "ai" | "api" }) {
  if (type === "user") return <User className="h-3.5 w-3.5 text-emerald-400" />;
  if (type === "ai") return <Cpu className="h-3.5 w-3.5 text-violet-400" />;
  return <Globe className="h-3.5 w-3.5 text-orange-400" />;
}

function SourceLabel({ type, label }: { type: "user" | "ai" | "api"; label?: string }) {
  const colors: Record<string, string> = {
    user: "bg-emerald-500/15 text-emerald-400",
    ai: "bg-violet-500/15 text-violet-400",
    api: "bg-orange-500/15 text-orange-400",
  };
  const defaultLabels: Record<string, string> = { user: "User Input", ai: "AI / LLM", api: "External API" };
  return (
    <span className={cn("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wider font-medium", colors[type])}>
      <SourceIcon type={type} />
      {label || defaultLabels[type]}
    </span>
  );
}

/* ─── Pipeline Flow Tab ─── */

function PipelineNode({ entry }: { entry: AuditEntry }) {
  const [expanded, setExpanded] = useState(false);
  const stageName = entry.summary?.split("→")[1]?.split(":")[0]?.trim() || entry.summary || "—";

  // Try to extract the stage key from the summary
  const stageKey = Object.keys(STAGE_META).find(
    (k) => entry.summary?.toLowerCase().includes(k.replace("_", " "))
  );
  const meta = stageKey ? STAGE_META[stageKey] : null;
  const iconType = meta?.icon || "ai";

  const hasInputs = entry.request_params && Object.keys(entry.request_params).length > 0;
  const hasOutputs = entry.response_summary && Object.keys(entry.response_summary).length > 0;
  const hasDetails = hasInputs || hasOutputs;

  let customLabel = undefined;
  if (iconType === "api" && (entry.decision?.toLowerCase().includes("serpapi") || entry.summary?.toLowerCase().includes("serpapi"))) {
    customLabel = "Serp API";
  }

  return (
    <div className="relative pl-8">
      {/* Timeline dot and line */}
      <div className="absolute left-0 top-0 flex flex-col items-center">
        <div className={cn(
          "flex h-6 w-6 items-center justify-center rounded-full border-2",
          iconType === "user" ? "border-emerald-500/50 bg-emerald-500/10" :
          iconType === "api" ? "border-orange-500/50 bg-orange-500/10" :
          "border-violet-500/50 bg-violet-500/10"
        )}>
          <SourceIcon type={iconType} />
        </div>
        <div className="w-px flex-1 bg-border/50 min-h-[16px]" />
      </div>

      <div
        className={cn(
          "mb-3 rounded border border-border/50 bg-card/50 p-3 transition-colors",
          hasDetails && "cursor-pointer hover:bg-muted/30",
        )}
        onClick={() => hasDetails && setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <SourceLabel type={iconType} label={customLabel} />
            <span className="text-sm font-medium truncate">{entry.summary || "—"}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="font-mono text-[10px] text-muted-foreground">
              {entry.occurred_at ? fmtTs(entry.occurred_at) : ""}
            </span>
            {entry.service && (
              <span className={cn("rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wider font-medium", SERVICE_COLORS[entry.service] ?? SERVICE_COLORS.internal)}>
                {entry.service}
              </span>
            )}
            {hasDetails && (
              expanded
                ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
            )}
          </div>
        </div>

        {/* Decision callout */}
        {Boolean(entry.request_params?.decision) && (
          <div className="mt-2 rounded bg-amber-500/5 border border-amber-500/20 px-3 py-1.5 text-xs text-amber-300">
            <strong>Decision:</strong> {String(entry.request_params!.decision)}
          </div>
        )}

        {expanded && (
          <div className="mt-3 space-y-3 border-t border-border/50 pt-3">
            {/* Prompt */}
            {Boolean(entry.request_params?.prompt) && (
              <div>
                <div className="mb-1 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  LLM Prompt
                </div>
                <pre className="overflow-x-auto rounded bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-purple-300 whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {String(entry.request_params!.prompt)}
                </pre>
              </div>
            )}

            {/* Inputs */}
            {Boolean(entry.request_params?.inputs) && (
              <div>
                <div className="mb-1 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  Input Variables
                </div>
                <pre className="overflow-x-auto rounded bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-sky-300 whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {JSON.stringify(entry.request_params!.inputs, null, 2)}
                </pre>
              </div>
            )}

            {/* Outputs */}
            {hasOutputs && (
              <div>
                <div className="mb-1 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  Output
                </div>
                <pre className="overflow-x-auto rounded bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-emerald-300 whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {JSON.stringify(entry.response_summary, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StrategyCard({ group }: { group: StrategyAuditGroup }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="border-card-border bg-card overflow-hidden">
      <button
        className="flex w-full items-center justify-between px-5 py-4 text-left hover:bg-muted/20 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <Layers className="h-5 w-5 text-primary shrink-0" />
          <div className="min-w-0">
            <div className="text-sm font-semibold truncate">{group.strategy_name}</div>
            <div className="text-[11px] text-muted-foreground">
              {group.events.length} events ·
              {group.event_counts.pipeline_stage ? ` ${group.event_counts.pipeline_stage} pipeline` : ""}
              {group.event_counts.api_call ? ` · ${group.event_counts.api_call} API calls` : ""}
              {(group.event_counts.strategy_change || group.event_counts.contact_change || group.event_counts.step_change)
                ? ` · ${(group.event_counts.strategy_change || 0) + (group.event_counts.contact_change || 0) + (group.event_counts.step_change || 0)} changes`
                : ""}
            </div>
          </div>
        </div>
        {expanded
          ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
          : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
        }
      </button>

      {expanded && (
        <div className="border-t border-border px-5 py-4">
          <div className="mb-4 flex items-center gap-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            <Workflow className="h-3.5 w-3.5" /> Unified Timeline (Newest First)
          </div>
          <div className="relative space-y-4 pl-4 border-l border-border/50">
            {group.events.map((e) => (
              <div key={e.id} className="relative">
                <div className="absolute -left-[21px] top-3 h-2 w-2 rounded-full border border-card bg-primary ring-1 ring-border/50" />
                {e.event_type === "pipeline_stage" && <PipelineNode entry={e} />}
                {e.event_type === "api_call" && <ApiCallRow entry={e} />}
                {e.event_type !== "pipeline_stage" && e.event_type !== "api_call" && <ChangeRow entry={e} />}
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function ApiCallRow({ entry }: { entry: AuditEntry }) {
  const [expanded, setExpanded] = useState(false);
  const serviceColor = SERVICE_COLORS[entry.service ?? "internal"] ?? SERVICE_COLORS.internal;
  const ok = entry.response_status != null && entry.response_status >= 200 && entry.response_status < 300;

  return (
    <div
      className={cn("rounded border border-border/30 px-3 py-2 text-xs transition-colors cursor-pointer hover:bg-muted/20", expanded && "bg-muted/10")}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={cn("rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wider font-medium shrink-0", serviceColor)}>
            {entry.service}
          </span>
          <span className="truncate text-foreground/80">{entry.summary || "—"}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {entry.response_status != null && (
            <span className={cn("font-mono text-[10px]", ok ? "text-primary" : "text-destructive")}>{entry.response_status}</span>
          )}
          <span className="font-mono text-[10px] text-muted-foreground">{entry.latency_ms != null ? `${entry.latency_ms}ms` : ""}</span>
          {entry.is_live ? <Wifi className="h-3 w-3 text-primary" /> : <WifiOff className="h-3 w-3 text-muted-foreground" />}
        </div>
      </div>
      {expanded && (
        <div className="mt-2 space-y-2 border-t border-border/30 pt-2">
          {entry.curl_command && (
            <pre className="overflow-x-auto rounded bg-black/40 p-2 font-mono text-[10px] text-green-300 whitespace-pre-wrap">{entry.curl_command}</pre>
          )}
          {entry.response_summary && Object.keys(entry.response_summary).length > 0 && (
            <pre className="overflow-x-auto rounded bg-black/40 p-2 font-mono text-[10px] text-sky-300 whitespace-pre-wrap">{JSON.stringify(entry.response_summary, null, 2)}</pre>
          )}
        </div>
      )}
    </div>
  );
}

function ChangeRow({ entry }: { entry: AuditEntry }) {
  const [expanded, setExpanded] = useState(false);
  const eventMeta = EVENT_LABELS[entry.event_type] ?? { label: entry.event_type, color: "bg-muted text-muted-foreground" };

  return (
    <div
      className={cn("rounded border border-border/30 px-3 py-2 text-xs transition-colors cursor-pointer hover:bg-muted/20", expanded && "bg-muted/10")}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={cn("rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wider font-medium", eventMeta.color)}>{eventMeta.label}</span>
          <span className="text-foreground/80">{entry.summary || "—"}</span>
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">{entry.occurred_at ? fmtTs(entry.occurred_at) : ""}</span>
      </div>
      {expanded && entry.change_field && (
        <div className="mt-2 grid grid-cols-2 gap-2 border-t border-border/30 pt-2">
          <div>
            <div className="mb-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">Before</div>
            <pre className="overflow-x-auto rounded bg-black/40 p-2 font-mono text-[10px] text-rose-300 whitespace-pre-wrap">{JSON.stringify(entry.change_before, null, 2)}</pre>
          </div>
          <div>
            <div className="mb-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">After</div>
            <pre className="overflow-x-auto rounded bg-black/40 p-2 font-mono text-[10px] text-emerald-300 whitespace-pre-wrap">{JSON.stringify(entry.change_after, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Raw Logs Tab (enhanced existing view) ─── */

function StatusBadge({ status }: { status: number | null }) {
  if (status == null) return <span className="text-muted-foreground">—</span>;
  const ok = status >= 200 && status < 300;
  return (
    <span className={cn("font-mono text-xs", ok ? "text-primary" : "text-destructive")}>
      {status}
    </span>
  );
}

function RawLogRow({ entry }: { entry: AuditEntry }) {
  const [expanded, setExpanded] = useState(false);
  const eventMeta = EVENT_LABELS[entry.event_type] ?? { label: entry.event_type, color: "bg-muted text-muted-foreground" };
  const serviceColor = SERVICE_COLORS[entry.service ?? "internal"] ?? SERVICE_COLORS.internal;
  const hasDetails =
    Boolean(entry.curl_command) ||
    entry.change_field != null ||
    (entry.request_params != null && Object.keys(entry.request_params).length > 0) ||
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
            <div className="space-y-3 py-2">
              {entry.curl_command && (
                <div>
                  <div className="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                    <Code2 className="h-3 w-3" /> cURL Replay
                  </div>
                  <pre className="overflow-x-auto rounded bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-green-300 whitespace-pre-wrap">
                    {entry.curl_command}
                  </pre>
                </div>
              )}
              {entry.request_params && Object.keys(entry.request_params).length > 0 && (
                <div>
                  <div className="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                    <Code2 className="h-3 w-3" /> Request / Inputs
                  </div>
                  <pre className="overflow-x-auto rounded bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-amber-300 whitespace-pre-wrap">
                    {JSON.stringify(entry.request_params, null, 2)}
                  </pre>
                </div>
              )}
              {entry.response_summary && Object.keys(entry.response_summary).length > 0 && (
                <div>
                  <div className="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                    <Code2 className="h-3 w-3" /> Response / Output
                  </div>
                  <pre className="overflow-x-auto rounded bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-sky-300 whitespace-pre-wrap">
                    {JSON.stringify(entry.response_summary, null, 2)}
                  </pre>
                </div>
              )}
              {entry.change_field && (
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
          </td>
        </tr>
      )}
    </>
  );
}

/* ─── Main Page ─── */

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

  // Raw logs
  const { data, isLoading, isError, error, refetch, isFetching } = useAuditLogs({
    strategy_id: strategyId || undefined,
    service: service || undefined,
    event_type: eventType || undefined,
    from_ts: fromTs,
    limit: LIMIT,
    offset,
  });

  // Grouped by strategy
  const { data: groupedData, isLoading: groupedLoading, refetch: groupedRefetch, isFetching: groupedFetching } = useAuditLogsByStrategy(fromTs, service);

  const logs = data?.logs ?? [];
  const total = data?.total ?? 0;
  const strategies = groupedData?.strategies ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Observability"
        title="Audit Log"
        subtitle="Complete pipeline data flow, API calls, and data changes — grouped by strategy with full input/output tracing."
      />

      <Tabs defaultValue="pipeline" className="space-y-4">
        <TabsList className="bg-muted/50">
          <TabsTrigger value="pipeline" className="gap-1.5">
            <Workflow className="h-3.5 w-3.5" /> Pipeline Flow
          </TabsTrigger>
          <TabsTrigger value="raw" className="gap-1.5">
            <ClipboardList className="h-3.5 w-3.5" /> Raw Logs
          </TabsTrigger>
        </TabsList>

        {/* ── Pipeline Flow Tab ── */}
        <TabsContent value="pipeline" className="space-y-4">
          <Card className="border-card-border bg-card p-4">
            <div className="flex flex-wrap items-center gap-3">
              <Select
                value={String(timeRange)}
                onValueChange={(v) => setTimeRange(Number(v))}
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
              
              <Select
                value={service || "all"}
                onValueChange={(v) => setService(v === "all" ? "" : v)}
              >
                <SelectTrigger className="h-8 w-44 text-xs">
                  <SelectValue placeholder="All Services" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Services</SelectItem>
                  <SelectItem value="s1_strategy">S1: Strategy Generation</SelectItem>
                  <SelectItem value="s2_signals">S2: Market Signals</SelectItem>
                  <SelectItem value="s3_outreach">S3: Outreach</SelectItem>
                  <SelectItem value="m3_intent">M3: Intent Tracking</SelectItem>
                  <SelectItem value="core">Core API</SelectItem>
                </SelectContent>
              </Select>

              <Button
                size="sm"
                variant="secondary"
                className="h-8 gap-1.5"
                onClick={() => groupedRefetch()}
                disabled={groupedFetching}
              >
                <RefreshCw className={cn("h-3 w-3", groupedFetching && "animate-spin")} />
                Refresh
              </Button>

              <div className="ml-auto text-xs text-muted-foreground">
                {strategies.length > 0 && <>{strategies.length} strategies</>}
              </div>
            </div>
          </Card>

          {/* Legend */}
          <div className="flex items-center gap-4 px-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1"><SourceIcon type="user" /> User Input</span>
            <span className="flex items-center gap-1"><SourceIcon type="ai" /> AI / LLM Decision</span>
            <span className="flex items-center gap-1"><SourceIcon type="api" /> External API</span>
          </div>

          {groupedLoading ? (
            <div className="flex items-center justify-center gap-2 p-12 text-sm text-muted-foreground">
              <RefreshCw className="h-4 w-4 animate-spin" /> Loading pipeline data…
            </div>
          ) : strategies.length === 0 ? (
            <div className="flex flex-col items-center gap-3 p-16 text-center">
              <Workflow className="h-8 w-8 text-muted-foreground/40" />
              <div className="text-sm font-medium text-foreground/70">No pipeline events yet</div>
              <div className="max-w-xs text-xs text-muted-foreground">
                Run a strategy generation (S1) to see the full data flow with inputs, prompts, and AI outputs.
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {strategies.map((group) => (
                <StrategyCard key={group.strategy_id} group={group} />
              ))}
            </div>
          )}
        </TabsContent>

        {/* ── Raw Logs Tab ── */}
        <TabsContent value="raw" className="space-y-4">
          <Card className="border-card-border bg-card p-4">
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
                  <SelectItem value="pipeline_stage">Pipeline Stages</SelectItem>
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
                  <SelectItem value="s1_strategy">S1 Strategy</SelectItem>
                  <SelectItem value="s2_signals">S2 Signals</SelectItem>
                  <SelectItem value="s3_outreach">S3 Outreach</SelectItem>
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
                      <RawLogRow key={entry.id} entry={entry} />
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
        </TabsContent>
      </Tabs>
    </>
  );
}
