import { Link } from "wouter";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/Pills";
import { useDashboardSummary, useDashboardActivity, useSignalPulse } from "@/hooks/useDashboard";
import { useStrategies } from "@/hooks/useStrategies";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { useCopilotFeed } from "@/hooks/useCopilot";
import { fmtRelative } from "@/lib/format";
import { ArrowUpRight, Plus, Zap, Target, Send, Layers, Radar, TrendingUp, TrendingDown } from "lucide-react";
import { ReasoningPanel } from "@/components/ReasoningPanel";

export function Dashboard() {
  const { data: summary, isLoading: sumLoading } = useDashboardSummary();
  const { data: activity } = useDashboardActivity();
  const { data: strategies } = useStrategies();
  const { activeId, active } = useActiveStrategy();
  const { data: plays } = useCopilotFeed(activeId ?? undefined);
  const { data: pulse } = useSignalPulse(activeId ?? undefined);

  return (
    <>
      <PageHeader
        eyebrow="Operating console"
        title={active ? active.product_name : "Welcome to GTM Factory"}
        subtitle="Live overview of your strategies, prospects, sequences, and intelligence loops."
        actions={
          <Link href="/strategy">
            <Button data-testid="button-new-strategy">
              <Plus className="mr-2 h-4 w-4" /> New strategy
            </Button>
          </Link>
        }
      />

      <ReasoningPanel
        title="How this dashboard is built"
        fallback={{
          source: "computed",
          logic:
            "Metrics are computed live from the database: strategies/contacts/sequences are direct counts, the top intent account is the highest-scoring Account row, and the prioritised plays come from the SDR Copilot ranker which orders Tier 1 contacts by recent signal recency and reply detection.",
          steps: [
            "Count strategies / contacts / sequences",
            "Pick max intent_score from Account",
            "Rank Tier 1 contacts by signal recency + reply state",
          ],
        }}
        className="mb-4"
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Strategies ready"
          value={sumLoading ? "—" : `${summary?.ready_strategies ?? 0} / ${summary?.strategies ?? 0}`}
          icon={<Layers className="h-4 w-4" />}
        />
        <MetricCard
          label="Total contacts"
          value={sumLoading ? "—" : (summary?.total_contacts ?? 0).toLocaleString()}
          icon={<Target className="h-4 w-4" />}
        />
        <MetricCard
          label="Tier 1 contacts"
          value={sumLoading ? "—" : (summary?.tier_1_contacts ?? 0).toLocaleString()}
          icon={<Zap className="h-4 w-4" />}
          accent
        />
        <MetricCard
          label="Live sequences"
          value={sumLoading ? "—" : (summary?.active_sequences ?? 0).toLocaleString()}
          icon={<Send className="h-4 w-4" />}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="col-span-2 border-card-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="text-sm font-semibold">Today's top plays</div>
            <Link
              href="/outreach"
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              All outreach <ArrowUpRight className="ml-0.5 inline h-3 w-3" />
            </Link>
          </div>
          {!activeId && (
            <div className="rounded border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              Select an active strategy to see your prioritised feed.
            </div>
          )}
          {activeId && (!plays || plays.length === 0) && (
            <div className="rounded border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              No top-tier contacts yet. Run lead discovery then score leads to populate.
            </div>
          )}
          <div className="space-y-2">
            {plays?.slice(0, 6).map((p) => (
              <div
                key={p.contact_id}
                className="flex items-center justify-between rounded border border-border bg-background/40 p-3 hover-elevate"
                data-testid={`play-${p.contact_id}`}
              >
                <div className="flex items-center gap-3">
                  <UrgencyDot urgency={p.urgency} />
                  <div>
                    <div className="text-sm font-medium">
                      {p.contact_name}
                      <span className="ml-2 text-xs text-muted-foreground">
                        {p.title}
                      </span>
                    </div>
                    <div className="mt-0.5 text-xs text-muted-foreground">
                      {p.action} — {p.reason}
                    </div>
                  </div>
                </div>
                <div className="text-right font-mono text-xs tabular-nums text-muted-foreground">
                  {p.score?.toFixed(0)}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-card-border bg-card p-5">
          <div className="mb-4 text-sm font-semibold">Top intent account</div>
          {summary?.top_intent_account ? (
            <div>
              <div className="text-lg font-semibold">
                {summary.top_intent_account.company_name}
              </div>
              <div className="mt-1 text-xs uppercase tracking-widest text-muted-foreground">
                {summary.top_intent_account.classification} intent
              </div>
              <div className="mt-4 font-mono text-3xl tabular-nums text-primary">
                {summary.top_intent_account.score.toFixed(0)}
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">
              No intent scored yet — visit Intelligence to recompute.
            </div>
          )}
          <div className="mt-6 border-t border-border pt-4">
            <div className="mb-2 text-xs font-medium uppercase tracking-widest text-muted-foreground">
              Activity
            </div>
            <div className="space-y-2">
              {activity?.slice(0, 6).map((a, i) => (
                <div key={i} className="flex items-start justify-between text-xs">
                  <div className="flex-1 truncate">
                    <span className="font-medium text-foreground">{a.title}</span>
                    <div className="truncate text-muted-foreground">{a.detail}</div>
                  </div>
                  <div className="ml-2 shrink-0 font-mono text-muted-foreground">
                    {fmtRelative(a.at)}
                  </div>
                </div>
              ))}
              {(!activity || activity.length === 0) && (
                <div className="text-xs text-muted-foreground">No activity yet.</div>
              )}
            </div>
          </div>
        </Card>
      </div>

      <SignalPulseCard pulse={pulse} />

      <div className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">All strategies</h2>
          <Link
            href="/strategy"
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Manage <ArrowUpRight className="ml-0.5 inline h-3 w-3" />
          </Link>
        </div>
        {!strategies && <Skeleton className="h-24 w-full" />}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {strategies?.map((s) => (
            <Link key={s.id} href={`/strategy/${s.id}`}>
              <Card
                className="cursor-pointer border-card-border bg-card p-4 hover-elevate"
                data-testid={`strategy-card-${s.id}`}
              >
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">{s.product_name}</div>
                  <StatusPill status={s.status} />
                </div>
                <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                  {s.description}
                </div>
                {s.target_market && (
                  <div className="mt-3 text-[11px] uppercase tracking-widest text-muted-foreground">
                    {s.target_market}
                  </div>
                )}
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}

function MetricCard({
  label,
  value,
  icon,
  accent,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <Card
      className={`border-card-border ${accent ? "bg-primary/5" : "bg-card"} p-4`}
    >
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          {label}
        </div>
        <div className="text-muted-foreground">{icon}</div>
      </div>
      <div className="mt-3 font-mono text-2xl tabular-nums text-foreground">
        {value}
      </div>
    </Card>
  );
}

function UrgencyDot({ urgency }: { urgency: string }) {
  const c =
    urgency === "high"
      ? "bg-destructive"
      : urgency === "medium"
        ? "bg-amber-500"
        : "bg-muted-foreground";
  return <span className={`h-2 w-2 rounded-full ${c}`} />;
}

function SignalPulseCard({ pulse }: { pulse?: import("@/hooks/useDashboard").SignalPulse }) {
  return (
    <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="col-span-2 border-card-border bg-card p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Radar className="h-4 w-4 text-primary" /> Signal Pulse
          </div>
          <Link
            href="/prospects"
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            All signals <ArrowUpRight className="ml-0.5 inline h-3 w-3" />
          </Link>
        </div>

        <div className="mb-3 flex items-center gap-4">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-2xl tabular-nums text-primary">
              {pulse?.new_signals ?? 0}
            </span>
            <span className="text-xs text-muted-foreground">
              signals from the last scan
            </span>
          </div>
          {pulse?.is_demo && (
            <span className="rounded bg-amber-500/10 px-2 py-0.5 text-[10px] uppercase tracking-widest text-amber-500">
              demo
            </span>
          )}
          <div className="ml-auto text-[11px] text-muted-foreground">
            {pulse?.last_scanned
              ? `Last scanned ${fmtRelative(pulse.last_scanned)}`
              : "Not scanned yet"}
          </div>
        </div>

        {pulse?.message && (
          <div className="rounded border border-dashed border-border p-3 text-xs text-muted-foreground">
            {pulse.message}
          </div>
        )}

        <div className="space-y-2">
          {pulse?.recent_signals?.slice(0, 5).map((s, i) => (
            <div
              key={i}
              className="rounded border border-border bg-background/40 p-3 text-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-foreground">
                  {s.company ?? "Account"}
                  <span className="ml-2 uppercase tracking-widest text-[10px] text-muted-foreground">
                    {s.signal_type}
                  </span>
                </span>
                {s.detected_at && (
                  <span className="font-mono text-muted-foreground">
                    {fmtRelative(s.detected_at)}
                  </span>
                )}
              </div>
              <div className="mt-1 text-muted-foreground">{s.summary}</div>
            </div>
          ))}
          {(!pulse?.recent_signals || pulse.recent_signals.length === 0) &&
            !pulse?.message && (
              <div className="rounded border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                No fresh signals yet.
              </div>
            )}
        </div>
      </Card>

      <Card className="border-card-border bg-card p-5">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
          <TrendingUp className="h-4 w-4 text-primary" /> Rank movers (24h)
        </div>
        <div className="space-y-2">
          {pulse?.top_movers?.slice(0, 5).map((m) => (
            <div
              key={m.contact_id}
              className="flex items-center justify-between rounded border border-border bg-background/40 p-3"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{m.contact_name}</div>
                <div className="truncate text-xs text-muted-foreground">
                  {m.company ?? m.title ?? ""}
                </div>
              </div>
              <div
                className={`ml-2 flex shrink-0 items-center gap-1 font-mono text-xs tabular-nums ${
                  m.delta >= 0 ? "text-emerald-500" : "text-destructive"
                }`}
              >
                {m.delta >= 0 ? (
                  <TrendingUp className="h-3 w-3" />
                ) : (
                  <TrendingDown className="h-3 w-3" />
                )}
                {m.delta >= 0 ? "+" : ""}
                {m.delta.toFixed(0)}
              </div>
            </div>
          ))}
          {(!pulse?.top_movers || pulse.top_movers.length === 0) && (
            <div className="rounded border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
              No rank changes yet.
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

