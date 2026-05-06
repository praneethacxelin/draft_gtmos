import { cn } from "@/lib/utils";

export function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    ready: "bg-primary/15 text-primary",
    generating: "bg-amber-500/15 text-amber-400",
    draft: "bg-muted text-muted-foreground",
    active: "bg-primary/15 text-primary",
    simulated: "bg-purple-500/15 text-purple-400",
    paused: "bg-amber-500/15 text-amber-400",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-widest",
        map[status] ?? "bg-muted text-muted-foreground",
      )}
    >
      {status}
    </span>
  );
}

export function TierBadge({ tier }: { tier?: number | null }) {
  if (!tier) return <span className="text-xs text-muted-foreground">—</span>;
  const map: Record<number, string> = {
    1: "border-primary/40 bg-primary/10 text-primary",
    2: "border-amber-500/40 bg-amber-500/10 text-amber-400",
    3: "border-border bg-muted text-muted-foreground",
  };
  return (
    <span
      className={cn(
        "inline-flex h-6 w-12 items-center justify-center rounded border text-[10px] font-semibold uppercase tracking-widest",
        map[tier],
      )}
    >
      Tier {tier}
    </span>
  );
}

export function ScoreBar({ value, color }: { value: number; color?: string }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-full max-w-[120px] overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full", color || "bg-primary")}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-mono text-xs tabular-nums text-foreground">
        {value.toFixed(0)}
      </span>
    </div>
  );
}

export function DemoBadge() {
  return (
    <span className="inline-flex items-center rounded border border-purple-500/40 bg-purple-500/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-purple-400">
      Demo
    </span>
  );
}

export function SentimentChip({ sentiment }: { sentiment: string }) {
  const map: Record<string, string> = {
    positive: "bg-primary/15 text-primary",
    neutral: "bg-muted text-muted-foreground",
    negative: "bg-destructive/15 text-destructive",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-widest",
        map[sentiment] ?? "bg-muted text-muted-foreground",
      )}
    >
      {sentiment}
    </span>
  );
}
