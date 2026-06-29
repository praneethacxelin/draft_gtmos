import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "wouter";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  BarChart3,
  BadgeCheck,
  Brain,
  CheckCircle2,
  Layers,
  Lightbulb,
  MessageSquareReply,
  Plus,
  Radar,
  Send,
  ShieldAlert,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/Pills";
import { ReasoningPanel } from "@/components/ReasoningPanel";
import { fmtRelative } from "@/lib/format";
import { apiFetch } from "@/lib/api";
import { useDashboardActivity, useDashboardSummary, useSignalPulse } from "@/hooks/useDashboard";
import { useStrategies, useCampaignPlan, type Strategy } from "@/hooks/useStrategies";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { useCopilotFeed } from "@/hooks/useCopilot";
import { useAccounts, usePrioritizedAccounts } from "@/hooks/useAccounts";
import { useSequenceByContact } from "@/hooks/useSequences";
import { useLearnings } from "@/hooks/useLearnings";
import { useExperimentBatches } from "@/hooks/useExperiments";
import { useEngagementEvents } from "@/hooks/useM3";

const DASHBOARD_MODE_KEY = "gtm-dashboard-mode";

type DashboardMode = "engineer" | "executive";

type Trend = "On Track" | "At Risk" | "Behind Plan";

interface RevenueTracking {
  opportunities: number;
  deal_size_usd: number | null;
  win_rate: number | null;
  win_rate_source: string;
  tracked_pipeline_usd: number;
  tracked_revenue_usd: number;
  projected_revenue_usd: number;
  attainment_pct: number;
}

interface OutreachAnalytics {
  total_sent: number;
  total_opened: number;
  total_clicked: number;
  total_replied: number;
  total_bounced: number;
  open_rate: number;
  click_rate: number;
  reply_rate: number;
  bounce_rate: number;
  revenue_tracking?: RevenueTracking;
  sequences: Array<{
    sequence_id: string;
    contact_name: string;
    strategy_name: string;
    status: string;
    open_rate: number;
    reply_rate: number;
  }>;
  by_strategy: Array<{
    strategy_id: string;
    strategy_name: string;
    sent: number;
    opened: number;
    clicked: number;
    replied: number;
    bounced: number;
    open_rate: number;
    reply_rate: number;
    revenue_tracking?: RevenueTracking;
  }>;
}

interface FunnelStageRow {
  stage: string;
  volume: number;
  conversionRate: number;
  dropOffRate: number;
}

interface StrategyPerformanceRow {
  strategy: Strategy;
  plannedInvestment: number;
  expectedReturn: number;
  currentProjection: number;
  pipelineGenerated: number;
  meetingsBooked: number;
  opportunitiesCreated: number;
  replyRate: number;
  roiMultiple: number;
  trend: Trend;
  varianceFromGoal: number;
}

function useOutreachAnalytics(strategyId?: string) {
  const qs = strategyId ? `?strategy_id=${strategyId}` : "";
  return useQuery<OutreachAnalytics>({
    queryKey: ["analytics", "outreach", strategyId ?? "all"],
    queryFn: () => apiFetch(`/api/analytics/outreach${qs}`),
    staleTime: 30_000,
  });
}

function readInitialMode(): DashboardMode {
  if (typeof window === "undefined") return "engineer";
  return window.localStorage.getItem(DASHBOARD_MODE_KEY) === "executive" ? "executive" : "engineer";
}

function formatMoney(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value >= 1_000_000 ? 1 : 0,
    notation: value >= 1_000_000 ? "compact" : "standard",
  }).format(value);
}

function formatPercent(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}%`;
}

function pickMoney(...values: Array<number | null | undefined>) {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) return value;
  }
  return 0;
}

function deriveDeliverabilityScore(analytics?: OutreachAnalytics) {
  if (!analytics) return null;
  const score = 100 - analytics.bounce_rate * 3 + analytics.open_rate * 0.2 + analytics.reply_rate * 0.3;
  return Math.max(0, Math.min(100, Math.round(score)));
}

function getWinningExperimentName(
  batch?: {
    best_experiment_id?: string | null;
    experiments?: { id?: string; name?: string | null; status?: string }[];
  },
) {
  const byId = batch?.experiments?.find((experiment) => experiment.id && experiment.id === batch?.best_experiment_id);
  if (byId?.name) return byId.name;
  const done = batch?.experiments?.find((experiment) => experiment.status === "done" && experiment.name);
  return done?.name ?? null;
}

function buildStrategyPerformanceRows(
  strategies: Strategy[] | undefined,
  analytics?: OutreachAnalytics,
): StrategyPerformanceRow[] {
  const analyticsByStrategy = new Map((analytics?.by_strategy ?? []).map((row) => [row.strategy_id, row]));

  return (strategies ?? [])
    .map((strategy) => {
      const analyticsRow = analyticsByStrategy.get(strategy.id);
      const roi = strategy.roi;
      const plannedInvestment = pickMoney(
        roi?.inputs?.investment_usd,
        roi?.gtm_plan?.costs?.planned_investment_usd,
        roi?.gtm_plan?.costs?.total_gtm_cost_usd,
        roi?.recommended_investment_usd,
      );
      const expectedReturn = pickMoney(
        roi?.inputs?.expected_revenue_usd,
        roi?.realistic_revenue_high_usd,
      );
      const currentProjection = pickMoney(
        roi?.calculator?.projected_revenue_usd,
        roi?.gtm_plan?.revenue_plan?.projected_total_usd,
        roi?.realistic_revenue_high_usd,
        expectedReturn,
      );
      const pipelineGenerated = pickMoney(
        roi?.calculator?.projected_pipeline_usd,
        roi?.gtm_plan?.revenue_plan?.projected_total_usd,
        roi?.gtm_plan?.reconciliation?.forward_revenue_usd,
      );
      const opportunitiesCreated = roi?.calculator?.deals_expected ?? roi?.gtm_plan?.required_closures ?? 0;
      const meetingsBooked = analyticsRow?.replied ?? 0;
      const replyRate = analyticsRow?.reply_rate ?? 0;
      const roiMultiple = plannedInvestment > 0 ? currentProjection / plannedInvestment : 0;
      const varianceFromGoal = currentProjection - expectedReturn;
      const trend: Trend =
        currentProjection >= expectedReturn && expectedReturn > 0
          ? "On Track"
          : currentProjection >= expectedReturn * 0.8
            ? "At Risk"
            : "Behind Plan";

      return {
        strategy,
        plannedInvestment,
        expectedReturn,
        currentProjection,
        pipelineGenerated,
        meetingsBooked,
        opportunitiesCreated,
        replyRate,
        roiMultiple,
        trend,
        varianceFromGoal,
      };
    })
    .sort((a, b) => b.roiMultiple - a.roiMultiple);
}

function buildRevenueFunnel(
  strategies: Strategy[] | undefined,
  summary: { total_contacts: number; tier_1_contacts: number; strategies: number } | undefined,
  analytics?: OutreachAnalytics,
): FunnelStageRow[] {
  const roiCount = (strategies ?? []).filter((strategy) => !!strategy.roi).length;
  const experimentCount = (strategies ?? []).filter((strategy) => !!strategy.roi?.gtm_plan?.experiment_plan?.n_experiments).length;
  const sent = analytics?.total_sent ?? 0;
  const replies = analytics?.total_replied ?? 0;
  const pipeline = (strategies ?? []).reduce((total, strategy) => {
    const row = buildStrategyPerformanceRows([strategy], analytics)[0];
    return total + row.pipelineGenerated;
  }, 0);

  const stages: Array<{ stage: string; volume: number }> = [
    { stage: "Discovery", volume: summary?.strategies ?? 0 },
    { stage: "ROI", volume: roiCount },
    { stage: "Experiments", volume: experimentCount },
    { stage: "Accounts", volume: summary?.total_contacts ?? 0 },
    { stage: "Contacts", volume: summary?.tier_1_contacts ?? 0 },
    { stage: "Outreach", volume: sent },
    { stage: "Meetings", volume: replies },
    { stage: "Pipeline", volume: pipeline },
  ];

  return stages.map((stage, index) => {
    const next = stages[index + 1];
    const conversionRate = next && stage.volume > 0 ? (next.volume / stage.volume) * 100 : 100;
    return {
      ...stage,
      conversionRate,
      dropOffRate: next ? Math.max(0, 100 - conversionRate) : 0,
    };
  });
}

function buildExecutiveAlerts(rows: StrategyPerformanceRow[], analytics?: OutreachAnalytics) {
  const alerts: { tone: "warn" | "good"; title: string; detail: string }[] = [];
  const lowRoi = rows.filter((row) => row.roiMultiple > 0 && row.roiMultiple < 3);
  if (lowRoi.length > 0) {
    alerts.push({
      tone: "warn",
      title: "ROI below target",
      detail: `${lowRoi.length} strategy${lowRoi.length === 1 ? "" : "ies"} are still below 3.0x ROI.`,
    });
  }
  if ((analytics?.reply_rate ?? 0) < 10 && (analytics?.total_sent ?? 0) > 0) {
    alerts.push({
      tone: "warn",
      title: "Reply rate declining",
      detail: `Overall reply rate is ${formatPercent(analytics?.reply_rate)}.`,
    });
  }
  const top = rows[0];
  if (top && top.roiMultiple >= 4) {
    alerts.push({
      tone: "good",
      title: "Strategy exceeding ROI target",
      detail: `${top.strategy.product_name} is running at ${top.roiMultiple.toFixed(1)}x ROI.`,
    });
  }
  return alerts.slice(0, 4);
}

export function Dashboard() {
  const { data: strategies } = useStrategies();
  const { activeId, active } = useActiveStrategy();
  const [mode, setMode] = useState<DashboardMode>(readInitialMode);

  useEffect(() => {
    window.localStorage.setItem(DASHBOARD_MODE_KEY, mode);
  }, [mode]);

  const selectedStrategy = active ?? strategies?.[0] ?? null;
  const selectedStrategyId = selectedStrategy?.id ?? activeId ?? undefined;

  return (
    <>
      <PageHeader
        eyebrow="Operating console"
        title={selectedStrategy ? selectedStrategy.product_name : "Welcome to GTM Factory"}
        subtitle={
          mode === "engineer"
            ? "GTM Engineer View keeps workflow, signals, sequences, and learnings in one place."
            : "CRO / Executive View compresses ROI, forecast, and revenue performance into one planning surface."
        }
        actions={
          <div className="flex items-center gap-2">
            <ModeToggle mode={mode} onChange={setMode} />
            <Link href="/strategy">
              <Button data-testid="button-new-strategy">
                <Plus className="mr-2 h-4 w-4" /> New strategy
              </Button>
            </Link>
          </div>
        }
      />

      <ReasoningPanel
        title="How this dashboard is built"
        fallback={{
          source: "computed",
          logic:
            "The dashboard uses live strategy, outreach, signal, learning, experiment, and ROI hooks. Only the view mode is persisted locally.",
          steps: [
            "Load the active strategy or first available strategy",
            "Compose the mode-specific cards from existing data hooks",
            "Persist the chosen mode in localStorage",
          ],
        }}
        className="mb-4"
      />

      {mode === "engineer" ? (
        <EngineerView strategyId={selectedStrategyId} selectedStrategy={selectedStrategy} />
      ) : (
        <ExecutiveView strategyId={selectedStrategyId} selectedStrategy={selectedStrategy} strategies={strategies} />
      )}

      <div className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">All strategies</h2>
          <Link href="/strategy" className="text-xs text-muted-foreground hover:text-foreground">
            Manage <ArrowUpRight className="ml-0.5 inline h-3 w-3" />
          </Link>
        </div>
        {!strategies && <Skeleton className="h-24 w-full" />}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {strategies?.map((strategy) => (
            <Link key={strategy.id} href={`/strategy/${strategy.id}`}>
              <Card className="cursor-pointer border-card-border bg-card p-4 hover-elevate" data-testid={`strategy-card-${strategy.id}`}>
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0 text-sm font-medium">{strategy.product_name}</div>
                  <StatusPill status={strategy.status} />
                </div>
                <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{strategy.description}</div>
                {strategy.target_market && (
                  <div className="mt-3 text-[11px] uppercase tracking-widest text-muted-foreground">{strategy.target_market}</div>
                )}
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}

function ModeToggle({ mode, onChange }: { mode: DashboardMode; onChange: (mode: DashboardMode) => void }) {
  return (
    <div className="inline-flex rounded border border-border bg-background p-1 text-xs shadow-sm">
      <button
        type="button"
        onClick={() => onChange("engineer")}
        className={`rounded px-3 py-1.5 font-medium transition-colors ${mode === "engineer" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
        data-testid="dashboard-mode-engineer"
      >
        GTM Engineer
      </button>
      <button
        type="button"
        onClick={() => onChange("executive")}
        className={`rounded px-3 py-1.5 font-medium transition-colors ${mode === "executive" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
        data-testid="dashboard-mode-executive"
      >
        CRO / Executive
      </button>
    </div>
  );
}

function EngineerView({ strategyId, selectedStrategy }: { strategyId?: string; selectedStrategy: Strategy | null }) {
  const { data: summary, isLoading: summaryLoading } = useDashboardSummary();
  const { data: activity } = useDashboardActivity();
  const { data: pulse } = useSignalPulse(strategyId);
  const { data: plays } = useCopilotFeed(strategyId);
  const { data: accounts } = useAccounts(strategyId);
  const { data: prioritized } = usePrioritizedAccounts(strategyId);
  const { data: learnings } = useLearnings({ strategyId });
  const { data: engagement } = useEngagementEvents(strategyId);
  const { data: batches } = useExperimentBatches(strategyId);
  const { data: campaignPlan } = useCampaignPlan(strategyId);

  const tiers = useMemo(
    () => ({
      tier1: prioritized?.tier_1?.length ?? 0,
      tier2: prioritized?.tier_2?.length ?? 0,
      tier3: prioritized?.tier_3?.length ?? 0,
    }),
    [prioritized],
  );

  const { data: sequence } = useSequenceByContact(plays?.[0]?.contact_id);
  const engagementCount = engagement?.filter((event) => ["reply", "replied", "interested", "meeting_booked"].includes(event.event_type)).length ?? 0;

  return (
    <>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <MetricCard label="Strategies ready" value={summaryLoading ? "—" : `${summary?.ready_strategies ?? 0} / ${summary?.strategies ?? 0}`} icon={<Layers className="h-4 w-4" />} />
        <MetricCard label="Total contacts" value={summaryLoading ? "—" : (summary?.total_contacts ?? accounts?.length ?? 0).toLocaleString()} icon={<Users className="h-4 w-4" />} />
        <MetricCard label="Tier 1 accounts" value={summaryLoading ? "—" : (summary?.tier_1_contacts ?? tiers.tier1).toLocaleString()} icon={<Zap className="h-4 w-4" />} accent />
        <MetricCard label="Captured learnings" value={(learnings?.length ?? 0).toString()} icon={<Sparkles className="h-4 w-4" />} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="col-span-2 border-card-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="text-sm font-semibold">Today's top plays</div>
            <Link href="/outreach" className="text-xs text-muted-foreground hover:text-foreground">
              All outreach <ArrowUpRight className="ml-0.5 inline h-3 w-3" />
            </Link>
          </div>
          {!strategyId && <EmptyState text="Select a strategy to see the prioritised feed." />}
          {strategyId && (!plays || plays.length === 0) && <EmptyState text="No top-tier contacts yet. Run lead discovery then score leads." />}
          <div className="space-y-2">
            {plays?.slice(0, 6).map((play) => (
              <div key={play.contact_id} className="flex items-center justify-between rounded border border-border bg-background/40 p-3 hover-elevate">
                <div className="flex items-center gap-3">
                  <UrgencyDot urgency={play.urgency} />
                  <div>
                    <div className="text-sm font-medium">
                      {play.contact_name}
                      <span className="ml-2 text-xs text-muted-foreground">{play.title}</span>
                    </div>
                    <div className="mt-0.5 text-xs text-muted-foreground">
                      {play.action} — {play.reason}
                    </div>
                  </div>
                </div>
                <div className="font-mono text-xs tabular-nums text-muted-foreground">{play.score?.toFixed(0)}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-card-border bg-card p-5">
          <div className="mb-4 text-sm font-semibold">Workflow funnel</div>
          <div className="space-y-3 text-sm">
            <FunnelRow label="Tier 1 accounts" value={tiers.tier1} accent />
            <FunnelRow label="Tier 2 accounts" value={tiers.tier2} />
            <FunnelRow label="Tier 3 accounts" value={tiers.tier3} />
            <FunnelRow label="Engaged events" value={engagementCount} />
            <FunnelRow label="Learnings" value={learnings?.length ?? 0} />
          </div>
          <div className="mt-6 border-t border-border pt-4">
            <div className="mb-2 text-xs font-medium uppercase tracking-widest text-muted-foreground">Active sequence</div>
            {sequence ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span className="text-foreground">{sequence.status}</span>
                  <span>{sequence.steps?.length ?? 0} steps</span>
                </div>
                <div>
                  Deliverability score: <span className="text-foreground">{sequence.deliverability_score ?? "—"}</span>
                </div>
                <div>
                  Latest launch: <span className="text-foreground">{sequence.campaigns?.[0]?.synced_at ? fmtRelative(sequence.campaigns[0].synced_at) : "none"}</span>
                </div>
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">Open a contact sequence to inspect send health.</div>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="border-card-border bg-card p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <div className="text-sm font-semibold">Experiment batches</div>
            <Link href="/strategy" className="text-xs text-muted-foreground hover:text-foreground">
              Open strategy <ArrowUpRight className="ml-0.5 inline h-3 w-3" />
            </Link>
          </div>
          <div className="space-y-3">
            {batches?.slice(0, 4).map((batch) => (
              <div key={batch.id} className="rounded border border-border bg-background/40 p-4 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium">{batch.name ?? "Experiment batch"}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {batch.n_experiments} experiments · {batch.leads_per_experiment} leads each
                    </div>
                  </div>
                  <span className="text-[10px] uppercase tracking-widest text-muted-foreground">{batch.status}</span>
                </div>
                <div className="mt-3 rounded border border-dashed border-border p-3 text-xs text-muted-foreground">
                  Winner: {getWinningExperimentName(batch) ?? "pending analysis"}
                  {batch.analysis?.winning_parameters_insight && (
                    <div className="mt-1">{batch.analysis.winning_parameters_insight}</div>
                  )}
                </div>
              </div>
            ))}
            {(!batches || batches.length === 0) && (
              <EmptyState text="No experiment batches yet. Start them from the Experiments panel." />
            )}
          </div>
        </Card>

        <Card className="border-card-border bg-card p-5">
          <div className="mb-4 text-sm font-semibold">Winning pipeline</div>
          <div className="space-y-3 text-sm">
            <FunnelRow label="Ready to launch" value={campaignPlan?.ready ? "Yes" : "No"} accent={!!campaignPlan?.ready} />
            <FunnelRow label="Winning experiment" value={campaignPlan?.winning_experiment_name ?? "Pending"} />
            <FunnelRow label="Pipeline window" value={campaignPlan?.experiment_window_months ? `${campaignPlan.experiment_window_months} mo` : "—"} />
          </div>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="border-card-border bg-card p-5 lg:col-span-2">
          <div className="mb-4 text-sm font-semibold">Approval queue</div>
          <div className="space-y-3">
            {(strategyId ? [selectedStrategy] : []).filter(Boolean).map((strategy) => (
              <div key={strategy!.id} className="rounded border border-border bg-background/40 p-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">{strategy!.product_name}</div>
                  <StatusPill status={strategy!.status} />
                </div>
              </div>
            ))}
            {(!strategyId || !selectedStrategy) && <EmptyState text="No active strategy selected." />}
          </div>
        </Card>

        <Card className="border-card-border bg-card p-5">
          <div className="mb-4 text-sm font-semibold">Recent activity</div>
          <div className="space-y-2">
            {activity?.slice(0, 6).map((item, index) => (
              <div key={index} className="flex items-start justify-between gap-3 text-xs">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-foreground">{item.title}</div>
                  <div className="truncate text-muted-foreground">{item.detail}</div>
                </div>
                <div className="shrink-0 font-mono text-muted-foreground">{fmtRelative(item.at)}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}

function ExecutiveView({
  strategyId,
  selectedStrategy,
  strategies,
}: {
  strategyId?: string;
  selectedStrategy: Strategy | null;
  strategies?: ReturnType<typeof useStrategies>["data"];
}) {
  const { data: summary, isLoading: summaryLoading } = useDashboardSummary();
  const { data: campaignPlan } = useCampaignPlan(strategyId);
  const { data: outreachAnalytics } = useOutreachAnalytics();
  const { data: activity } = useDashboardActivity();

  const performanceRows = useMemo(() => buildStrategyPerformanceRows(strategies, outreachAnalytics), [strategies, outreachAnalytics]);
  const funnel = useMemo(() => buildRevenueFunnel(strategies, summary, outreachAnalytics), [strategies, summary, outreachAnalytics]);
  const alerts = useMemo(() => buildExecutiveAlerts(performanceRows, outreachAnalytics), [performanceRows, outreachAnalytics]);

  const totals = useMemo(() => {
    const activeStrategies = strategies?.length ?? summary?.strategies ?? 0;
    const investment = performanceRows.reduce((sum, row) => sum + row.plannedInvestment, 0);
    const pipelineGenerated = performanceRows.reduce((sum, row) => sum + row.pipelineGenerated, 0);
    const revenueInfluenced = performanceRows.reduce((sum, row) => sum + row.currentProjection, 0);
    const opportunitiesCreated = performanceRows.reduce((sum, row) => sum + row.opportunitiesCreated, 0);
    const meetingsBooked = performanceRows.reduce((sum, row) => sum + row.meetingsBooked, 0);
    const roiMultiple = investment > 0 ? revenueInfluenced / investment : 0;
    return { activeStrategies, investment, pipelineGenerated, revenueInfluenced, opportunitiesCreated, meetingsBooked, roiMultiple };
  }, [performanceRows, strategies, summary]);

  const topRow = performanceRows[0];
  const forecastTarget = pickMoney(
    selectedStrategy?.roi?.inputs?.revenue_target_usd,
    campaignPlan?.annual_target_usd,
    topRow?.expectedReturn,
  );
  const forecastedRevenue = pickMoney(
    selectedStrategy?.roi?.calculator?.projected_revenue_usd,
    topRow?.currentProjection,
  );
  const forecastConfidence: string =
    campaignPlan?.overall_confidence ??
    (topRow?.trend === "On Track" ? "High" : topRow?.trend === "At Risk" ? "Moderate" : "Low");
  const projectedRoi = topRow?.roiMultiple ?? 0;

  return (
    <>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-8">
        <MetricCard label="Active strategies" value={totals.activeStrategies.toString()} icon={<Layers className="h-4 w-4" />} accent />
        <MetricCard label="GTM investment" value={formatMoney(totals.investment)} icon={<Target className="h-4 w-4" />} />
        <MetricCard label="Pipeline generated" value={formatMoney(totals.pipelineGenerated)} icon={<BarChart3 className="h-4 w-4" />} accent />
        <MetricCard label="Revenue influenced" value={formatMoney(totals.revenueInfluenced)} icon={<BadgeCheck className="h-4 w-4" />} />
        <MetricCard label="Opportunities created" value={totals.opportunitiesCreated.toLocaleString()} icon={<Sparkles className="h-4 w-4" />} accent />
        <MetricCard label="Meetings booked" value={totals.meetingsBooked.toLocaleString()} icon={<MessageSquareReply className="h-4 w-4" />} />
        <MetricCard label="Overall ROI multiple" value={totals.roiMultiple ? `${totals.roiMultiple.toFixed(1)}x` : "—"} icon={<CheckCircle2 className="h-4 w-4" />} accent />
        <MetricCard label="Projected revenue" value={formatMoney(forecastedRevenue)} icon={<BarChart3 className="h-4 w-4" />} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="col-span-2 border-card-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="text-sm font-semibold">Strategy performance table</div>
            <Link href="/strategy" className="text-xs text-muted-foreground hover:text-foreground">
              Strategy hub <ArrowUpRight className="ml-0.5 inline h-3 w-3" />
            </Link>
          </div>
          <div className="overflow-hidden rounded border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[10px] uppercase tracking-widest text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Strategy</th>
                  <th className="px-3 py-2 text-right">Investment</th>
                  <th className="px-3 py-2 text-right">Expected return</th>
                  <th className="px-3 py-2 text-right">Projection</th>
                  <th className="px-3 py-2 text-right">Pipeline</th>
                  <th className="px-3 py-2 text-right">Meetings</th>
                  <th className="px-3 py-2 text-right">Opps</th>
                  <th className="px-3 py-2 text-right">Reply</th>
                  <th className="px-3 py-2 text-right">ROI</th>
                  <th className="px-3 py-2 text-left">Trend</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {performanceRows.map((row) => (
                  <tr key={row.strategy.id} className="text-xs hover:bg-background/40">
                    <td className="px-3 py-2">
                      <div className="font-medium text-foreground">{row.strategy.product_name}</div>
                      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{row.strategy.status}</div>
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{formatMoney(row.plannedInvestment)}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{formatMoney(row.expectedReturn)}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{formatMoney(row.currentProjection)}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{formatMoney(row.pipelineGenerated)}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{row.meetingsBooked.toLocaleString()}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{row.opportunitiesCreated.toLocaleString()}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{formatPercent(row.replyRate)}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{row.roiMultiple ? `${row.roiMultiple.toFixed(1)}x` : "—"}</td>
                    <td className="px-3 py-2">
                      <span className={`rounded px-2 py-1 text-[10px] uppercase tracking-widest ${row.trend === "On Track" ? "bg-emerald-500/10 text-emerald-500" : row.trend === "At Risk" ? "bg-amber-500/10 text-amber-500" : "bg-destructive/10 text-destructive"}`}>
                        {row.trend}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="border-card-border bg-card p-5">
          <div className="mb-4 text-sm font-semibold">Forecast</div>
          <div className="space-y-3 text-sm">
            <FunnelRow label="Quarter revenue target" value={formatMoney(forecastTarget)} accent />
            <FunnelRow label="Forecasted revenue" value={formatMoney(forecastedRevenue)} />
            <FunnelRow label="Forecast confidence" value={forecastConfidence} />
            <FunnelRow label="Projected ROI" value={projectedRoi ? `${projectedRoi.toFixed(1)}x` : "—"} />
          </div>
          {outreachAnalytics?.revenue_tracking && (
            <div className="mt-5 border-t border-border pt-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Tracked vs plan
                </div>
                <span className="rounded bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                  from {outreachAnalytics.revenue_tracking.opportunities} live repl{outreachAnalytics.revenue_tracking.opportunities === 1 ? "y" : "ies"}
                </span>
              </div>
              <div className="space-y-3 text-sm">
                <FunnelRow label="Tracked revenue (closed-loop)" value={formatMoney(outreachAnalytics.revenue_tracking.tracked_revenue_usd)} accent />
                <FunnelRow label="Tracked pipeline" value={formatMoney(outreachAnalytics.revenue_tracking.tracked_pipeline_usd)} />
              </div>
              <div className="mt-3">
                <div className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>Plan attainment</span>
                  <span className="font-mono tabular-nums">{outreachAnalytics.revenue_tracking.attainment_pct.toFixed(1)}%</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${Math.min(100, outreachAnalytics.revenue_tracking.attainment_pct)}%` }}
                  />
                </div>
              </div>
            </div>
          )}
          <div className="mt-6 border-t border-border pt-4 text-xs text-muted-foreground">
            Tracked revenue is the closed loop: live email replies valued at the ROI deal size × win rate, measured against the plan's projection.
          </div>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="border-card-border bg-card p-5">
          <div className="mb-4 text-sm font-semibold">Revenue funnel</div>
          <div className="space-y-3">
            {funnel.map((stage, index) => (
              <div key={stage.stage} className="rounded border border-border bg-background/40 p-3 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-foreground">
                    {index + 1}. {stage.stage}
                  </div>
                  <div className="font-mono tabular-nums text-muted-foreground">{stage.volume.toLocaleString()}</div>
                </div>
                <div className="mt-2 flex items-center justify-between text-[11px] uppercase tracking-widest text-muted-foreground">
                  <span>Conversion {stage.conversionRate.toFixed(1)}%</span>
                  <span>Drop-off {stage.dropOffRate.toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-card-border bg-card p-5">
          <div className="mb-4 text-sm font-semibold">Executive alerts</div>
          <div className="space-y-2">
            {alerts.length > 0 ? (
              alerts.map((alert) => (
                <div
                  key={alert.title}
                  className={`rounded border p-3 text-xs ${alert.tone === "good" ? "border-emerald-500/20 bg-emerald-500/5" : "border-amber-500/20 bg-amber-500/5"}`}
                >
                  <div className="font-medium text-foreground">{alert.title}</div>
                  <div className="mt-1 text-muted-foreground">{alert.detail}</div>
                </div>
              ))
            ) : (
              <EmptyState text="No business-impact alerts at the moment." />
            )}
          </div>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="border-card-border bg-card p-5">
          <div className="mb-4 text-sm font-semibold">Business activity</div>
          <div className="space-y-2">
            {activity?.slice(0, 6).map((item, index) => (
              <div key={index} className="flex items-start justify-between gap-3 text-xs">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-foreground">{item.title}</div>
                  <div className="truncate text-muted-foreground">{item.detail}</div>
                </div>
                <div className="shrink-0 font-mono text-muted-foreground">{fmtRelative(item.at)}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-card-border bg-card p-5">
          <div className="mb-4 text-sm font-semibold">Readiness context</div>
          <div className="space-y-2 text-sm text-muted-foreground">
            <div className="rounded border border-border bg-background/40 p-3">
              Selected strategy: <span className="text-foreground">{selectedStrategy?.product_name ?? "none"}</span>
            </div>
            <div className="rounded border border-border bg-background/40 p-3">
              Campaign gate: <span className="text-foreground">{campaignPlan?.ready ? "ready" : campaignPlan?.gate ?? "pending"}</span>
            </div>
            <div className="rounded border border-border bg-background/40 p-3">
              Ready strategies: <span className="text-foreground">{summaryLoading ? "—" : `${summary?.ready_strategies ?? 0}`}</span>
            </div>
          </div>
        </Card>
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
  icon: ReactNode;
  accent?: boolean;
}) {
  return (
    <Card className={`border-card-border ${accent ? "bg-primary/5" : "bg-card"} p-4`}>
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">{label}</div>
        <div className="text-muted-foreground">{icon}</div>
      </div>
      <div className="mt-3 font-mono text-2xl tabular-nums text-foreground">{value}</div>
    </Card>
  );
}

function FunnelRow({
  label,
  value,
  accent,
}: {
  label: string;
  value: number | string;
  accent?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between rounded border px-3 py-2 ${accent ? "border-primary/30 bg-primary/5" : "border-border bg-background/40"}`}>
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-mono text-sm tabular-nums text-foreground">{value}</span>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded border border-dashed border-border p-4 text-center text-xs text-muted-foreground">{text}</div>;
}

function UrgencyDot({ urgency }: { urgency: string }) {
  const c = urgency === "high" ? "bg-destructive" : urgency === "medium" ? "bg-amber-500" : "bg-muted-foreground";
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
          <Link href="/prospects" className="text-xs text-muted-foreground hover:text-foreground">
            All signals <ArrowUpRight className="ml-0.5 inline h-3 w-3" />
          </Link>
        </div>
        <div className="mb-3 flex items-center gap-4">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-2xl tabular-nums text-primary">{pulse?.new_signals ?? 0}</span>
            <span className="text-xs text-muted-foreground">signals from the last scan</span>
          </div>
          {pulse?.is_demo && (
            <span className="rounded bg-amber-500/10 px-2 py-0.5 text-[10px] uppercase tracking-widest text-amber-500">
              demo
            </span>
          )}
          <div className="ml-auto text-[11px] text-muted-foreground">
            {pulse?.last_scanned ? `Last scanned ${fmtRelative(pulse.last_scanned)}` : "Not scanned yet"}
          </div>
        </div>
        {pulse?.message && (
          <div className="rounded border border-dashed border-border p-3 text-xs text-muted-foreground">
            {pulse.message}
          </div>
        )}
        <div className="space-y-2">
          {pulse?.recent_signals?.slice(0, 5).map((signal, index) => (
            <div key={index} className="rounded border border-border bg-background/40 p-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-medium text-foreground">
                  {signal.company ?? "Account"}
                  <span className="ml-2 uppercase tracking-widest text-[10px] text-muted-foreground">
                    {signal.signal_type}
                  </span>
                </span>
                {signal.detected_at && <span className="font-mono text-muted-foreground">{fmtRelative(signal.detected_at)}</span>}
              </div>
              <div className="mt-1 text-muted-foreground">{signal.summary}</div>
            </div>
          ))}
          {(!pulse?.recent_signals || pulse.recent_signals.length === 0) && !pulse?.message && (
            <EmptyState text="No fresh signals yet." />
          )}
        </div>
      </Card>

      <Card className="border-card-border bg-card p-5">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
          <TrendingUp className="h-4 w-4 text-primary" /> Rank movers (24h)
        </div>
        <div className="space-y-2">
          {pulse?.top_movers?.slice(0, 5).map((mover) => (
            <div key={mover.contact_id} className="flex items-center justify-between rounded border border-border bg-background/40 p-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{mover.contact_name}</div>
                <div className="truncate text-xs text-muted-foreground">{mover.company ?? mover.title ?? ""}</div>
              </div>
              <div className={`ml-2 flex shrink-0 items-center gap-1 font-mono text-xs tabular-nums ${mover.delta >= 0 ? "text-emerald-500" : "text-destructive"}`}>
                {mover.delta >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                {mover.delta >= 0 ? "+" : ""}
                {mover.delta.toFixed(0)}
              </div>
            </div>
          ))}
          {(!pulse?.top_movers || pulse.top_movers.length === 0) && <EmptyState text="No rank changes yet." />}
        </div>
      </Card>
    </div>
  );
}
