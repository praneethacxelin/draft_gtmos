import { useState } from "react";
import { ChevronDown, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Provenance, ProvenanceSource, WithProvenance } from "@/hooks/useStrategies";

const SOURCE_META: Record<
  ProvenanceSource,
  { label: string; className: string; live: boolean }
> = {
  ai_generated: {
    label: "AI generated",
    className: "bg-purple-500/15 text-purple-600 dark:text-purple-300 border-purple-500/30",
    live: false,
  },
  serpapi: {
    label: "Live · SerpAPI",
    className: "bg-blue-500/15 text-blue-600 dark:text-blue-300 border-blue-500/30",
    live: true,
  },
  apollo: {
    label: "Live · Apollo",
    className: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border-emerald-500/30",
    live: true,
  },
  instantly: {
    label: "Live · Instantly",
    className: "bg-amber-500/15 text-amber-600 dark:text-amber-300 border-amber-500/30",
    live: true,
  },
  clay: {
    label: "Live · Clay",
    className: "bg-cyan-500/15 text-cyan-600 dark:text-cyan-300 border-cyan-500/30",
    live: true,
  },
  computed: {
    label: "Computed",
    className: "bg-primary/15 text-primary border-primary/30",
    live: false,
  },
  legacy: {
    label: "Legacy data",
    className: "bg-muted text-muted-foreground border-border",
    live: false,
  },
};

export function SourceBadge({ source }: { source: ProvenanceSource }) {
  const meta = SOURCE_META[source] ?? SOURCE_META.legacy;
  return (
    <Badge variant="outline" className={cn("gap-1 text-xs font-normal", meta.className)}>
      {meta.label}
    </Badge>
  );
}

export interface ReasoningPanelProps {
  title?: string;
  provenance?: Provenance | null;
  fallback?: { source: ProvenanceSource; logic: string; steps?: string[] };
  defaultOpen?: boolean;
  className?: string;
}

export function ReasoningPanel({
  title = "How this was generated",
  provenance,
  fallback,
  defaultOpen = false,
  className,
}: ReasoningPanelProps) {
  const [open, setOpen] = useState(defaultOpen);
  const data: Partial<Provenance> | null = provenance
    ? provenance
    : fallback
    ? {
        source: fallback.source,
        logic: fallback.logic,
        steps: fallback.steps ?? [],
        counts: {},
        generated_at: "",
      }
    : null;
  if (!data || !data.source) return null;
  const meta = SOURCE_META[data.source] ?? SOURCE_META.legacy;
  const generatedAt = data.generated_at
    ? new Date(data.generated_at).toLocaleString()
    : null;

  return (
    <Card className={cn("border-dashed", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover-elevate active-elevate-2 rounded-md"
        data-testid="button-reasoning-toggle"
      >
        <div className="flex items-center gap-2 min-w-0">
          <Sparkles className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="text-sm font-medium truncate">{title}</span>
          <SourceBadge source={data.source} />
          {!meta.live && data.source !== "computed" && data.source !== "legacy" ? (
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
              demo
            </span>
          ) : null}
        </div>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform shrink-0",
            open && "rotate-180",
          )}
        />
      </button>
      {open && (
        <div className="space-y-3 border-t px-4 py-3 text-sm">
          {data.logic && <p className="text-muted-foreground">{data.logic}</p>}
          {data.steps && data.steps.length > 0 && (
            <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
              {data.steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          )}
          {data.counts && Object.keys(data.counts).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(data.counts).map(([k, v]) => (
                <Badge key={k} variant="secondary" className="font-mono text-xs">
                  {k}: {String(v)}
                </Badge>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {data.model && <span>Model: <code>{data.model}</code></span>}
            {generatedAt && <span>{generatedAt}</span>}
          </div>
        </div>
      )}
    </Card>
  );
}

/** Synthesize a fallback provenance descriptor for legacy data without a stamp. */
export function fallbackProvenance(
  obj: WithProvenance | null | undefined,
  source: ProvenanceSource,
  logic: string,
  steps?: string[],
): { source: ProvenanceSource; logic: string; steps?: string[] } | undefined {
  if (obj && obj._provenance) return undefined;
  return { source, logic, steps };
}
