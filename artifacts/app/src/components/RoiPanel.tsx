import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  Calculator,
  Sparkles,
  Info,
  Users,
  Layers,
  Target,
  Gauge,
  GitBranch,
  Lightbulb,
  Calendar,
  Mail,
  FlaskConical,
  PieChart,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ReasoningPanel } from "@/components/ReasoningPanel";
import {
  useValidateRoi,
  usePersonaIntelligence,
  usePersonaAllocation,
  type Strategy,
  type RoiVerdict,
  type GtmPlan,
  type CampaignMode,
  type RevenueAssessment,
  type PersonaScore,
} from "@/hooks/useStrategies";

/** Parse a money-ish string ("$1.5M", "1,500,000", "250k") into a number. */
function parseMoney(raw: unknown): number | null {
  if (raw == null) return null;
  if (typeof raw === "number") return Number.isFinite(raw) ? raw : null;
  if (typeof raw !== "string") return null;
  let s = raw.replace(/[$,\s]/g, "").replace(/usd/i, "").toLowerCase();
  if (!s) return null;
  let mult = 1;
  if (s.endsWith("bn")) { mult = 1e9; s = s.slice(0, -2); }
  else if (s.endsWith("b")) { mult = 1e9; s = s.slice(0, -1); }
  else if (s.endsWith("m")) { mult = 1e6; s = s.slice(0, -1); }
  else if (s.endsWith("k")) { mult = 1e3; s = s.slice(0, -1); }
  const n = Number(s);
  return Number.isFinite(n) ? n * mult : null;
}

function fmtMoney(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toLocaleString()}`;
}

const VERDICT_META: Record<
  RoiVerdict,
  { label: string; icon: typeof CheckCircle2; cls: string }
> = {
  realistic: {
    label: "Realistic",
    icon: CheckCircle2,
    cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-500",
  },
  too_optimistic: {
    label: "Too optimistic",
    icon: TrendingUp,
    cls: "border-amber-500/30 bg-amber-500/10 text-amber-500",
  },
  too_conservative: {
    label: "Too conservative",
    icon: TrendingDown,
    cls: "border-sky-500/30 bg-sky-500/10 text-sky-500",
  },
  insufficient_data: {
    label: "Insufficient data",
    icon: Info,
    cls: "border-muted-foreground/30 bg-muted/40 text-muted-foreground",
  },
};

const TIMEFRAME_OPTIONS = [3, 6, 12, 18, 24, 36];

function parseTimeframe(raw: unknown): number {
  if (typeof raw === "number") return raw;
  if (typeof raw === "string") {
    const m = raw.match(/\d+/);
    if (m) return Number(m[0]);
  }
  return 12;
}

function fmtInt(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return Math.round(v).toLocaleString();
}

const URGENCY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

const SALES_CYCLE_OPTIONS = [
  { value: 1, label: "1 month" },
  { value: 2, label: "2 months" },
  { value: 3, label: "3 months (1 quarter)" },
  { value: 6, label: "6 months" },
  { value: 9, label: "9 months" },
  { value: 12, label: "12 months" },
];

const MONTH_OPTIONS = [
  { value: 1, label: "January" },
  { value: 2, label: "February" },
  { value: 3, label: "March" },
  { value: 4, label: "April" },
  { value: 5, label: "May" },
  { value: 6, label: "June" },
  { value: 7, label: "July" },
  { value: 8, label: "August" },
  { value: 9, label: "September" },
  { value: 10, label: "October" },
  { value: 11, label: "November" },
  { value: 12, label: "December" },
];

const CONFIDENCE_META: Record<string, string> = {
  High: "border-emerald-500/30 bg-emerald-500/10 text-emerald-500",
  Moderate: "border-amber-500/30 bg-amber-500/10 text-amber-500",
  Low: "border-destructive/30 bg-destructive/10 text-destructive",
};

// Cold-safe sending days per month used in the email feasibility copy.
const SENDING_DAYS = 21;

const ASSESSMENT_META: Record<
  RevenueAssessment,
  { cls: string }
> = {
  Conservative: { cls: "border-sky-500/30 bg-sky-500/10 text-sky-500" },
  Realistic: { cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-500" },
  Aggressive: { cls: "border-amber-500/30 bg-amber-500/10 text-amber-500" },
  Unrealistic: { cls: "border-destructive/30 bg-destructive/10 text-destructive" },
};

const RECON_META: Record<string, { cls: string; title: string }> = {
  above_realistic: {
    cls: "border-amber-500/30 bg-amber-500/10 text-amber-500",
    title: "Target is above the market-grounded range",
  },
  within_realistic: {
    cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-500",
    title: "Target is within the realistic range",
  },
  below_realistic: {
    cls: "border-sky-500/30 bg-sky-500/10 text-sky-500",
    title: "Target is below the realistic range",
  },
  unknown: {
    cls: "border-card-border bg-background/40 text-muted-foreground",
    title: "Run Market Sizing for a grounded comparison",
  },
};

export function RoiPanel({
  strategyId,
  strategy,
}: {
  strategyId: string;
  strategy: Strategy;
}) {
  const dd = (strategy.discovery_data ?? {}) as Record<string, unknown>;
  const roi = strategy.roi ?? null;

  const [investment, setInvestment] = useState<string>(() =>
    roi?.inputs?.investment_usd != null
      ? String(roi.inputs.investment_usd)
      : typeof dd.planned_investment === "string"
        ? dd.planned_investment
        : "",
  );
  const [expected, setExpected] = useState<string>(() =>
    roi?.inputs?.expected_revenue_usd != null
      ? String(roi.inputs.expected_revenue_usd)
      : typeof dd.expected_revenue === "string"
        ? dd.expected_revenue
        : "",
  );
  const [timeframe, setTimeframe] = useState<number>(() =>
    roi?.inputs?.timeframe_months ?? parseTimeframe(dd.roi_timeframe),
  );
  const [segment, setSegment] = useState<string>(
    () => roi?.inputs?.market_segment ?? "",
  );

  // ---- GTM planning assumptions (additive layer on top of the ROI check) ----
  // Revenue target is the single "Expected revenue / return" value above — the
  // GTM plan is built on the same figure that drives the feasibility verdict.
  const [avgDealSize, setAvgDealSize] = useState<string>(() =>
    roi?.inputs?.average_deal_size_usd != null
      ? String(roi.inputs.average_deal_size_usd)
      : "",
  );
  const [conversionPct, setConversionPct] = useState<number>(() =>
    roi?.inputs?.conversion_rate != null
      ? Math.round(roi.inputs.conversion_rate * 1000) / 10
      : 1,
  );
  const [leadCost, setLeadCost] = useState<number>(
    () => roi?.inputs?.lead_acquisition_cost ?? 0.3,
  );
  const [outreachCost, setOutreachCost] = useState<number>(
    () => roi?.inputs?.outreach_cost ?? 0.5,
  );
  const [engineerCapacity, setEngineerCapacity] = useState<number>(
    () => roi?.inputs?.gtm_engineer_capacity ?? 10,
  );
  const [currentEngineers, setCurrentEngineers] = useState<number>(
    () => roi?.inputs?.current_gtm_engineers ?? 1,
  );
  const [urgency, setUrgency] = useState<string>(
    () => roi?.inputs?.time_urgency ?? "medium",
  );
  const [campaignCount, setCampaignCount] = useState<number>(
    () => roi?.inputs?.campaign_count ?? 3,
  );
  const [salesCycle, setSalesCycle] = useState<number>(
    () => roi?.inputs?.sales_cycle_months ?? 3,
  );
  const [startMonth, setStartMonth] = useState<number>(
    () => roi?.inputs?.execution_start_month ?? new Date().getMonth() + 1,
  );
  const [serpCost, setSerpCost] = useState<number>(
    () => roi?.gtm_plan?.inputs?.serp_api_cost ?? 0.1,
  );
  const [tokenCost, setTokenCost] = useState<number>(
    () => roi?.gtm_plan?.inputs?.ai_token_cost ?? 0.05,
  );
  const [emailAccounts, setEmailAccounts] = useState<number>(
    () => roi?.gtm_plan?.inputs?.email_accounts ?? 2,
  );
  const [emailAccountType, setEmailAccountType] = useState<string>(
    () => roi?.gtm_plan?.inputs?.email_account_type ?? "workspace",
  );

  // True when the inputs were carried over from the discovery questionnaire
  // (and not yet overwritten by a saved validation run), so we can tell the
  // user we already have their answers instead of asking again.
  const prefilledFromDiscovery =
    !roi &&
    (typeof dd.planned_investment === "string" && dd.planned_investment.trim() !== "" ||
      typeof dd.expected_revenue === "string" && dd.expected_revenue.trim() !== "");

  const validate = useValidateRoi();

  const investNum = parseMoney(investment);
  const expectedNum = parseMoney(expected);
  const liveMultiple = useMemo(() => {
    if (!investNum || expectedNum == null) return null;
    return Math.round((expectedNum / investNum) * 100) / 100;
  }, [investNum, expectedNum]);

  const canSubmit = !!investNum && investNum > 0 && expectedNum != null && expectedNum >= 0;

  function submit() {
    if (!canSubmit) return;
    const avgDealSizeNum = parseMoney(avgDealSize);
    validate.mutate({
      id: strategyId,
      data: {
        investment_usd: investNum!,
        expected_revenue_usd: expectedNum!,
        timeframe_months: timeframe,
        market_segment: segment.trim() || null,
        // GTM plan reuses the expected revenue as its target (single source).
        revenue_target_usd: expectedNum,
        average_deal_size_usd: avgDealSizeNum,
        conversion_rate: Math.max(0.0001, conversionPct / 100),
        lead_acquisition_cost: Math.max(0, Number(leadCost) || 0),
        outreach_cost: Math.max(0, Number(outreachCost) || 0),
        gtm_engineer_capacity: Math.max(1, Number(engineerCapacity) || 10),
        current_gtm_engineers: Math.max(0, Math.round(Number(currentEngineers) || 0)),
        time_urgency: urgency,
        campaign_count: Math.max(1, Math.round(Number(campaignCount) || 1)),
        sales_cycle_months: Math.max(1, Math.round(Number(salesCycle) || 3)),
        execution_start_month: Math.min(12, Math.max(1, Math.round(Number(startMonth) || 1))),
        serp_api_cost: Math.max(0, Number(serpCost) || 0),
        ai_token_cost: Math.max(0, Number(tokenCost) || 0),
        email_accounts: Math.max(0, Math.round(Number(emailAccounts) || 0)),
        email_account_type: emailAccountType,
      },
    });
  }

  const verdict = roi?.verdict;
  const vmeta = verdict ? VERDICT_META[verdict] : null;
  const VIcon = vmeta?.icon;

  return (
    <div className="space-y-4">
      <ReasoningPanel
        provenance={roi?._provenance}
        fallback={{
          source: "ai_generated",
          logic:
            "ROI expectation is validated against this profile's own TAM/SAM/SOM and ICP. The model proposes profile-specific benchmarks (ROI multiple, payback, ACV, win rate) and a corrected target; revenue ceilings vs the market size are enforced deterministically.",
          steps: [
            "Read planned investment + expected revenue",
            "Compare against profile market sizing + ICP",
            "Flag if revenue breaches TAM / SAM / SOM ceilings",
            "Propose corrected investment or revenue target",
          ],
        }}
      />

      {/* ---- Inputs ---- */}
      <Card className="border-card-border bg-card p-5">
        <div className="mb-4 flex items-center gap-2">
          <Calculator className="h-4 w-4 text-primary" />
          <div className="text-sm font-semibold">ROI Expectation Check</div>
          {prefilledFromDiscovery && (
            <span className="ml-auto inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-500">
              <Sparkles className="h-3 w-3" />
              Prefilled from discovery
            </span>
          )}
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label className="text-xs">Planned GTM investment</Label>
            <Input
              value={investment}
              onChange={(e) => setInvestment(e.target.value)}
              placeholder="e.g., $250,000"
              className="mt-1"
              data-testid="input-roi-investment"
            />
            <div className="mt-1 text-[11px] text-muted-foreground">
              {investNum != null ? fmtMoney(investNum) : "Enter a dollar amount"}
            </div>
          </div>
          <div>
            <Label className="text-xs">Expected revenue / return</Label>
            <Input
              value={expected}
              onChange={(e) => setExpected(e.target.value)}
              placeholder="e.g., $1,500,000"
              className="mt-1"
              data-testid="input-roi-expected"
            />
            <div className="mt-1 text-[11px] text-muted-foreground">
              {expectedNum != null ? fmtMoney(expectedNum) : "Enter a dollar amount"}
            </div>
          </div>
          <div>
            <Label className="text-xs">Timeframe</Label>
            <Select
              value={String(timeframe)}
              onValueChange={(v) => setTimeframe(Number(v))}
            >
              <SelectTrigger className="mt-1 h-9 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIMEFRAME_OPTIONS.map((m) => (
                  <SelectItem key={m} value={String(m)}>
                    {m} months
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Market segment (optional)</Label>
            <Input
              value={segment}
              onChange={(e) => setSegment(e.target.value)}
              placeholder="e.g., Healthcare AI, mid-market"
              className="mt-1"
              data-testid="input-roi-segment"
            />
          </div>
        </div>

        {/* ---- GTM planning assumptions ---- */}
        <div className="mt-5 border-t border-card-border pt-4">
          <div className="mb-3 flex items-center gap-2">
            <Target className="h-4 w-4 text-primary" />
            <div className="text-sm font-semibold">GTM Planning Assumptions</div>
            <span className="text-[11px] text-muted-foreground">
              Used to size prospect volume, cost, team &amp; campaigns
            </span>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div>
              <Label className="text-xs">Average deal size</Label>
              <Input
                value={avgDealSize}
                onChange={(e) => setAvgDealSize(e.target.value)}
                placeholder="e.g., $10,000"
                className="mt-1"
                data-testid="input-gtm-deal-size"
              />
              <div className="mt-1 text-[11px] text-muted-foreground">
                {parseMoney(avgDealSize) != null
                  ? fmtMoney(parseMoney(avgDealSize))
                  : "Defaults to benchmark ACV"}
              </div>
            </div>
            <div>
              <Label className="text-xs">Conversion rate (%)</Label>
              <Input
                type="number"
                min={0.01}
                step={0.1}
                value={conversionPct}
                onChange={(e) => setConversionPct(Number(e.target.value))}
                className="mt-1"
                data-testid="input-gtm-conversion"
              />
              <div className="mt-1 text-[11px] text-muted-foreground">
                Prospects → closed deals
              </div>
            </div>
            <div>
              <Label className="text-xs">Lead acquisition cost ($/lead)</Label>
              <Input
                type="number"
                min={0}
                step={0.05}
                value={leadCost}
                onChange={(e) => setLeadCost(Number(e.target.value))}
                className="mt-1"
                data-testid="input-gtm-lead-cost"
              />
            </div>
            <div>
              <Label className="text-xs">Outreach cost ($/prospect)</Label>
              <Input
                type="number"
                min={0}
                step={0.05}
                value={outreachCost}
                onChange={(e) => setOutreachCost(Number(e.target.value))}
                className="mt-1"
                data-testid="input-gtm-outreach-cost"
              />
            </div>
            <div>
              <Label className="text-xs">Engineer capacity (prospects/day)</Label>
              <Input
                type="number"
                min={1}
                step={1}
                value={engineerCapacity}
                onChange={(e) => setEngineerCapacity(Number(e.target.value))}
                className="mt-1"
                data-testid="input-gtm-capacity"
              />
            </div>
            <div>
              <Label className="text-xs">Current GTM engineers</Label>
              <Input
                type="number"
                min={0}
                step={1}
                value={currentEngineers}
                onChange={(e) => setCurrentEngineers(Number(e.target.value))}
                className="mt-1"
                data-testid="input-gtm-engineers"
              />
            </div>
            <div>
              <Label className="text-xs">Time urgency</Label>
              <Select value={urgency} onValueChange={setUrgency}>
                <SelectTrigger className="mt-1 h-9 text-sm" data-testid="select-gtm-urgency">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {URGENCY_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Campaign count</Label>
              <Input
                type="number"
                min={1}
                step={1}
                value={campaignCount}
                onChange={(e) => setCampaignCount(Number(e.target.value))}
                className="mt-1"
                data-testid="input-gtm-campaign-count"
              />
            </div>
            <div>
              <Label className="text-xs">Sales cycle duration</Label>
              <Select
                value={String(salesCycle)}
                onValueChange={(v) => setSalesCycle(Number(v))}
              >
                <SelectTrigger className="mt-1 h-9 text-sm" data-testid="select-gtm-sales-cycle">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SALES_CYCLE_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={String(o.value)}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Execution start month</Label>
              <Select
                value={String(startMonth)}
                onValueChange={(v) => setStartMonth(Number(v))}
              >
                <SelectTrigger className="mt-1 h-9 text-sm" data-testid="select-gtm-start-month">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MONTH_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={String(o.value)}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Email accounts</Label>
              <Input
                type="number"
                min={0}
                step={1}
                value={emailAccounts}
                onChange={(e) => setEmailAccounts(Number(e.target.value))}
                className="mt-1"
                data-testid="input-gtm-email-accounts"
              />
            </div>
            <div>
              <Label className="text-xs">Email account type</Label>
              <Select value={emailAccountType} onValueChange={setEmailAccountType}>
                <SelectTrigger className="mt-1 h-9 text-sm" data-testid="select-gtm-email-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="workspace">Google Workspace / paid (50/day)</SelectItem>
                  <SelectItem value="free">Free Gmail / Outlook (30/day)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">SERP / enrichment cost ($/prospect)</Label>
              <Input
                type="number"
                min={0}
                step={0.01}
                value={serpCost}
                onChange={(e) => setSerpCost(Number(e.target.value))}
                className="mt-1"
                data-testid="input-gtm-serp-cost"
              />
            </div>
            <div>
              <Label className="text-xs">AI token cost ($/prospect)</Label>
              <Input
                type="number"
                min={0}
                step={0.01}
                value={tokenCost}
                onChange={(e) => setTokenCost(Number(e.target.value))}
                className="mt-1"
                data-testid="input-gtm-token-cost"
              />
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button
            onClick={submit}
            disabled={!canSubmit || validate.isPending}
            data-testid="button-validate-roi"
            className="gap-2"
          >
            <Sparkles className="h-4 w-4" />
            {validate.isPending ? "Validating…" : "Validate expectation"}
          </Button>
          {liveMultiple != null && (
            <div className="text-xs text-muted-foreground">
              Implied return:{" "}
              <span className="font-mono font-semibold text-foreground">
                {liveMultiple}x
              </span>
            </div>
          )}
        </div>
        {validate.isError && (
          <div className="mt-3 flex items-start gap-2 rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{(validate.error as Error)?.message ?? "Validation failed"}</span>
          </div>
        )}
      </Card>

      {/* ---- Result ---- */}
      {roi ? (
        <div className="space-y-4">
          {/* Verdict */}
          {vmeta && VIcon && (
            <Card className={`border p-4 ${vmeta.cls}`}>
              <div className="flex items-start gap-3">
                <VIcon className="mt-0.5 h-5 w-5 shrink-0" />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold">{vmeta.label}</span>
                    {roi.expected_multiple != null && (
                      <span className="rounded bg-background/40 px-1.5 py-0.5 font-mono text-[11px]">
                        {roi.expected_multiple}x expected
                      </span>
                    )}
                  </div>
                  {roi.headline && (
                    <div className="mt-1 text-sm opacity-90">{roi.headline}</div>
                  )}
                </div>
              </div>
            </Card>
          )}

          {/* Warnings */}
          {(roi.warnings ?? []).length > 0 && (
            <Card className="border-amber-500/30 bg-amber-500/5 p-4">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-amber-500">
                <AlertTriangle className="h-3.5 w-3.5" />
                Reality checks
              </div>
              <ul className="space-y-1.5 text-sm text-foreground/90">
                {roi.warnings!.map((w, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-amber-500">•</span>
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Corrections */}
          {(roi.corrections ?? []).length > 0 && (
            <Card className="border-card-border bg-card p-4">
              <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Suggested corrections
              </div>
              <div className="space-y-2">
                {roi.corrections!.map((c, i) => (
                  <div
                    key={i}
                    className="rounded border border-card-border bg-background/40 p-3 text-sm"
                  >
                    <div className="flex items-center gap-2 font-medium">
                      <span className="capitalize">
                        {c.field === "expected_revenue" ? "Expected revenue" : "Investment"}
                      </span>
                      <span className="font-mono text-muted-foreground line-through">
                        {fmtMoney(c.from_usd)}
                      </span>
                      <span className="text-muted-foreground">→</span>
                      <span className="font-mono font-semibold text-primary">
                        {fmtMoney(c.to_usd)}
                      </span>
                    </div>
                    {c.reason && (
                      <div className="mt-1 text-xs text-muted-foreground">{c.reason}</div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Realistic range + benchmarks */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Card className="border-card-border bg-card p-4">
              <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                Realistic revenue range
              </div>
              <div className="mt-2 font-mono text-2xl tabular-nums text-foreground">
                {fmtMoney(roi.realistic_revenue_low_usd)} –{" "}
                {fmtMoney(roi.realistic_revenue_high_usd)}
              </div>
              {roi.recommended_investment_usd != null && (
                <div className="mt-2 text-xs text-muted-foreground">
                  Recommended investment:{" "}
                  <span className="font-mono text-foreground">
                    {fmtMoney(roi.recommended_investment_usd)}
                  </span>
                </div>
              )}
            </Card>

            {roi.benchmark && (
              <Card className="border-card-border bg-card p-4">
                <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  Profile benchmarks
                </div>
                <dl className="mt-2 space-y-1 text-sm">
                  {roi.benchmark.typical_roi_multiple_low != null && (
                    <BenchRow
                      k="Typical ROI multiple"
                      v={`${roi.benchmark.typical_roi_multiple_low}–${roi.benchmark.typical_roi_multiple_high}x`}
                    />
                  )}
                  {roi.benchmark.typical_payback_months != null && (
                    <BenchRow
                      k="Payback period"
                      v={`${roi.benchmark.typical_payback_months} mo`}
                    />
                  )}
                  {roi.benchmark.avg_contract_value_usd != null && (
                    <BenchRow
                      k="Avg. contract value"
                      v={fmtMoney(roi.benchmark.avg_contract_value_usd)}
                    />
                  )}
                  {roi.benchmark.typical_win_rate_pct != null && (
                    <BenchRow
                      k="Win rate"
                      v={`${roi.benchmark.typical_win_rate_pct}%`}
                    />
                  )}
                  {roi.benchmark.typical_sales_cycle_months != null && (
                    <BenchRow
                      k="Sales cycle"
                      v={`${roi.benchmark.typical_sales_cycle_months} mo`}
                    />
                  )}
                </dl>
                {roi.benchmark.note && (
                  <div className="mt-2 text-[11px] text-muted-foreground">
                    {roi.benchmark.note}
                  </div>
                )}
              </Card>
            )}
          </div>

          {/* Calculator */}
          {roi.calculator && (
            <Card className="border-card-border bg-card p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                <Calculator className="h-3.5 w-3.5" />
                ROI calculator
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <CalcStat label="Accounts reachable" value={roi.calculator.accounts_reachable?.toLocaleString()} />
                <CalcStat label="Deals expected" value={roi.calculator.deals_expected?.toLocaleString()} />
                <CalcStat label="Projected pipeline" value={fmtMoney(roi.calculator.projected_pipeline_usd)} />
                <CalcStat label="Projected revenue" value={fmtMoney(roi.calculator.projected_revenue_usd)} />
              </div>
              {(roi.calculator.assumptions ?? []).length > 0 && (
                <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
                  {roi.calculator.assumptions!.map((a, i) => (
                    <li key={i} className="flex gap-2">
                      <span>•</span>
                      <span>{a}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {/* GTM planning engine */}
          {roi.gtm_plan && <GtmPlanSection plan={roi.gtm_plan} />}

          {/* Persona intelligence */}
          <PersonaIntelligenceSection
            strategyId={strategyId}
            totalProspects={roi.gtm_plan?.required_prospects ?? null}
          />

          {/* Rationale + market ceiling */}
          {roi.rationale && (
            <Card className="border-card-border bg-card p-4">
              <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                Rationale
              </div>
              <div className="mt-1 text-sm text-muted-foreground">{roi.rationale}</div>
            </Card>
          )}

          {roi.market_context &&
            (roi.market_context.tam_usd != null ||
              roi.market_context.sam_usd != null ||
              roi.market_context.som_usd != null) && (
              <Card className="border-card-border bg-card p-4">
                <div className="mb-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  Market ceiling used
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  {(["tam_usd", "sam_usd", "som_usd"] as const).map((k) => (
                    <div key={k}>
                      <div className="text-[10px] uppercase text-muted-foreground">
                        {k.replace("_usd", "").toUpperCase()}
                      </div>
                      <div className="font-mono text-sm text-foreground">
                        {fmtMoney(roi.market_context?.[k] ?? undefined)}
                      </div>
                    </div>
                  ))}
                </div>
                {!strategy.tam_sam_som && (
                  <div className="mt-2 text-[11px] text-amber-500">
                    Tip: run Market Sizing first for a sharper, market-grounded ROI check.
                  </div>
                )}
              </Card>
            )}
        </div>
      ) : (
        <div className="rounded border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          Enter your planned investment and expected revenue, then validate to
          see whether the expectation is realistic for this product profile.
        </div>
      )}
    </div>
  );
}

function BenchRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="font-mono text-foreground">{v}</dd>
    </div>
  );
}

function CalcStat({ label, value }: { label: string; value?: string }) {
  return (
    <div className="rounded border border-card-border bg-background/40 p-3">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg tabular-nums text-foreground">
        {value ?? "—"}
      </div>
    </div>
  );
}

function PersonaIntelligenceSection({
  strategyId,
  totalProspects,
}: {
  strategyId: string;
  totalProspects?: number | null;
}) {
  const { data, isLoading } = usePersonaIntelligence(strategyId);
  const { data: allocation } = usePersonaAllocation(strategyId, totalProspects);

  if (isLoading) {
    return (
      <Card className="border-card-border bg-card p-4">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          <Users className="h-3.5 w-3.5" />
          Persona intelligence
        </div>
        <div className="mt-2 text-sm text-muted-foreground">Scoring personas…</div>
      </Card>
    );
  }

  const personas = (data?.personas ?? []).filter((p) => p.contacts > 0);
  if (!data || personas.length === 0) {
    return (
      <Card className="border-card-border bg-card p-4">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          <Users className="h-3.5 w-3.5" />
          Persona intelligence
        </div>
        <div className="mt-2 text-sm text-muted-foreground">
          No persona performance data yet. Run prospecting and outreach to learn which buyer
          personas convert best — this panel scores them automatically from funnel activity.
        </div>
      </Card>
    );
  }

  const maxScore = Math.max(...personas.map((p) => p.score), 1);

  return (
    <Card className="border-card-border bg-card p-4">
      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        <Users className="h-3.5 w-3.5" />
        Persona intelligence
        <span className="ml-auto inline-flex items-center gap-2 text-[11px] font-normal normal-case tracking-normal text-muted-foreground">
          {data.total_contacts} contacts ·{" "}
          {data.data_basis === "funnel" ? "funnel-based" : "early signal"}
        </span>
      </div>
      <div className="mb-3 text-[11px] text-muted-foreground">
        Each persona is scored 0–100 from how its contacts actually move through the funnel —
        reply rate, progression depth, conversions, and response speed.
      </div>

      <div className="space-y-2">
        {personas.map((p) => (
          <PersonaRow key={p.persona_type} p={p} maxScore={maxScore} />
        ))}
      </div>

      {allocation && allocation.allocations.length > 0 && (
        <div className="mt-3 border-t border-card-border pt-3">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            <PieChart className="h-3.5 w-3.5" />
            Prospecting allocation
            {allocation.total_prospects != null && (
              <span className="ml-auto font-normal normal-case tracking-normal">
                {fmtInt(allocation.total_prospects)} prospects to split
              </span>
            )}
          </div>
          <div className="space-y-2">
            {allocation.allocations.map((a) => (
              <div
                key={a.persona_type}
                className="rounded border border-card-border bg-background/40 p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-foreground">{a.label}</span>
                  <span className="text-[11px] text-muted-foreground">
                    rank #{a.rank} · score {a.score}
                  </span>
                  <span className="ml-auto font-mono text-sm font-semibold text-primary">
                    {a.weight_pct}%
                  </span>
                  {a.prospect_count > 0 && (
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {fmtInt(a.prospect_count)} prospects
                    </span>
                  )}
                </div>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-card-border/60">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.max(2, a.weight_pct)}%` }}
                  />
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                  {a.reply_rate_pct != null && <span>First response {a.reply_rate_pct}%</span>}
                  {a.avg_funnel_depth != null && <span>Funnel depth {a.avg_funnel_depth}</span>}
                </div>
              </div>
            ))}
          </div>
          {(allocation.notes ?? []).map((note, i) => (
            <div
              key={i}
              className="mt-2 flex items-start gap-2 text-[11px] text-muted-foreground"
            >
              <Info className="mt-0.5 h-3 w-3 shrink-0" />
              <span>{note}</span>
            </div>
          ))}
        </div>
      )}

      {(data.recommendations ?? []).length > 0 && (
        <div className="mt-3 border-t border-card-border pt-3">
          <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            <Lightbulb className="h-3.5 w-3.5" />
            Persona recommendations
          </div>
          <ul className="space-y-1.5 text-sm text-foreground/90">
            {data.recommendations.map((r, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-primary">•</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function PersonaRow({ p, maxScore }: { p: PersonaScore; maxScore: number }) {
  const cls = CONFIDENCE_META[p.confidence] ?? CONFIDENCE_META.Moderate;
  const gradeColor =
    p.score >= 75
      ? "text-emerald-500"
      : p.score >= 50
        ? "text-sky-500"
        : p.score >= 30
          ? "text-amber-500"
          : "text-destructive";
  const barColor =
    p.score >= 75
      ? "bg-emerald-500"
      : p.score >= 50
        ? "bg-sky-500"
        : p.score >= 30
          ? "bg-amber-500"
          : "bg-destructive";
  const m = p.metrics;
  return (
    <div className="rounded border border-card-border bg-background/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-foreground">{p.label}</span>
        <span className="text-[11px] text-muted-foreground">{p.contacts} contacts</span>
        <span
          className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-medium ${cls}`}
        >
          {p.confidence} confidence
        </span>
        <span className={`ml-auto font-mono text-sm font-semibold ${gradeColor}`}>{p.score}</span>
        <span className={`text-[11px] ${gradeColor}`}>{p.grade}</span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-card-border/60">
        <div
          className={`h-full rounded-full ${barColor}`}
          style={{ width: `${Math.max(2, (p.score / maxScore) * 100)}%` }}
        />
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        <span>Reply {m.reply_rate_pct}%</span>
        <span>Open {m.open_rate_pct}%</span>
        <span>Qualified {fmtInt(m.qualified)}</span>
        <span>Conversions {fmtInt(m.conversions)}</span>
        {m.conversion_value_usd > 0 && <span>Value {fmtMoney(m.conversion_value_usd)}</span>}
        {m.avg_response_hours != null && <span>Avg reply {Math.round(m.avg_response_hours)}h</span>}
      </div>
    </div>
  );
}

function GtmPlanSection({ plan }: { plan: GtmPlan }) {
  const costs = plan.costs ?? {};
  const cap = plan.capacity ?? {};
  const planInputs = plan.inputs ?? {};
  const assessment = plan.revenue_assessment;
  const aMeta = assessment ? ASSESSMENT_META[assessment] : null;
  const rec = plan.reconciliation;
  const emailCap = plan.email_capacity;
  const exp = plan.experiment_plan;
  const dealSize = planInputs.average_deal_size_usd;
  const targetUsd = planInputs.revenue_target_usd;
  const convPct =
    planInputs.conversion_rate != null
      ? Math.round(planInputs.conversion_rate * 1000) / 10
      : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 pt-1">
        <Target className="h-4 w-4 text-primary" />
        <div className="text-sm font-semibold">GTM Feasibility</div>
        <span className="text-[11px] text-muted-foreground">
          Prospect volume · platform cost · team · email & experiment readiness
        </span>
      </div>

      {/* Revenue assessment + requirement headline */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card className={`border p-4 ${aMeta?.cls ?? "border-card-border bg-card"}`}>
          <div className="text-[10px] font-medium uppercase tracking-widest opacity-80">
            Revenue assessment
          </div>
          <div className="mt-1 text-2xl font-semibold">{assessment ?? "—"}</div>
        </Card>
        <Card className="border-card-border bg-card p-4">
          <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Prospects needed
          </div>
          <div className="mt-1 font-mono text-2xl tabular-nums text-foreground">
            {fmtInt(plan.required_prospects)}
          </div>
          {convPct != null && (
            <div className="mt-1 text-[10px] text-muted-foreground">
              {fmtInt(plan.required_closures)} deals ÷ {convPct}% conversion
            </div>
          )}
        </Card>
        <Card className="border-card-border bg-card p-4">
          <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Deals needed
          </div>
          <div className="mt-1 font-mono text-2xl tabular-nums text-foreground">
            {fmtInt(plan.required_closures)}
          </div>
          {dealSize != null && (
            <div className="mt-1 text-[10px] text-muted-foreground">
              {fmtMoney(targetUsd)} target ÷ {fmtMoney(dealSize)} deal size
            </div>
          )}
        </Card>
      </div>

      {/* GTM investment required (platform cost) */}
      <Card className="border-card-border bg-card p-4">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          <Calculator className="h-3.5 w-3.5" />
          Expected GTM investment (platform cost)
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <CalcStat
            label="Lead acquisition"
            value={fmtMoney(costs.lead_acquisition_cost_usd)}
          />
          <CalcStat
            label="Outreach"
            value={fmtMoney(costs.outreach_cost_usd)}
          />
          <CalcStat
            label="SERP / enrichment"
            value={fmtMoney(costs.serp_api_cost_usd)}
          />
          <CalcStat
            label="AI tokens"
            value={fmtMoney(costs.ai_token_cost_usd)}
          />
          <CalcStat
            label="Total GTM cost"
            value={fmtMoney(costs.total_gtm_cost_usd)}
          />
        </div>
        <div className="mt-2 text-[11px] text-muted-foreground">
          {fmtInt(plan.required_prospects)} prospects ×{" "}
          {fmtMoney(planInputs.lead_acquisition_cost)} lead +{" "}
          {fmtMoney(planInputs.outreach_cost)} outreach +{" "}
          {fmtMoney(planInputs.serp_api_cost)} SERP +{" "}
          {fmtMoney(planInputs.ai_token_cost)} AI tokens per prospect ={" "}
          {fmtMoney(costs.total_gtm_cost_usd)} total platform cost.
        </div>
        {costs.planned_investment_usd != null && (
          <div
            className={`mt-3 text-xs ${costs.budget_sufficient ? "text-emerald-500" : "text-amber-500"}`}
          >
            {costs.budget_sufficient
              ? `Planned investment of ${fmtMoney(costs.planned_investment_usd)} covers the required GTM spend.`
              : `Planned investment of ${fmtMoney(costs.planned_investment_usd)} is below the required GTM spend of ${fmtMoney(costs.total_gtm_cost_usd)}.`}
          </div>
        )}
      </Card>

      {/* Team capacity */}
      <Card className="border-card-border bg-card p-4">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          <Users className="h-3.5 w-3.5" />
          GTM team capacity
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <CalcStat label="Available (prospects)" value={fmtInt(cap.available_capacity)} />
          <CalcStat label="Required (prospects)" value={fmtInt(cap.required_capacity)} />
          <CalcStat
            label="Utilization"
            value={cap.utilization_pct != null ? `${cap.utilization_pct}%` : "—"}
          />
          <CalcStat label="Capacity gap" value={fmtInt(cap.capacity_gap)} />
        </div>
        <div className="mt-2 text-[11px] text-muted-foreground">
          Capacity is the number of prospects the team can work over the{" "}
          {planInputs.time_horizon_months ?? "—"}-month horizon:{" "}
          {fmtInt(cap.current_engineers)} engineer(s) × {planInputs.gtm_engineer_capacity ?? "—"}/day ×{" "}
          {fmtInt(cap.working_days)} working days = {fmtInt(cap.available_capacity)} prospects.
        </div>
        <div
          className={`mt-3 flex items-start gap-2 rounded border px-3 py-2 text-xs ${
            cap.sufficient
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500"
              : "border-amber-500/30 bg-amber-500/10 text-amber-500"
          }`}
        >
          {cap.sufficient ? (
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          ) : (
            <Gauge className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          )}
          <span>
            {cap.message}
            {!cap.sufficient && (cap.additional_engineers ?? 0) > 0 && (
              <>
                {" "}
                Current team: {fmtInt(cap.current_engineers)} engineer(s); recommended:{" "}
                {fmtInt(cap.recommended_engineers)} (hire{" "}
                <span className="font-semibold">{fmtInt(cap.additional_engineers)}</span>{" "}
                more).
              </>
            )}
          </span>
        </div>
      </Card>

      {/* Email sending feasibility (cold-safe) */}
      {emailCap && (
        <Card className="border-card-border bg-card p-4">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            <Mail className="h-3.5 w-3.5" />
            Email sending feasibility
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <CalcStat label="Inboxes" value={fmtInt(emailCap.email_accounts)} />
            <CalcStat
              label="Per inbox / day"
              value={`${fmtInt(emailCap.per_account_per_day)} (${emailCap.email_account_type === "free" ? "free" : "workspace"})`}
            />
            <CalcStat label="Monthly capacity" value={fmtInt(emailCap.monthly_capacity)} />
            <CalcStat label="Total capacity" value={fmtInt(emailCap.total_capacity)} />
          </div>
          <div className="mt-2 text-[11px] text-muted-foreground">
            {fmtInt(emailCap.email_accounts)} inbox(es) ×{" "}
            {fmtInt(emailCap.per_account_per_day)} cold-safe sends/day ×{" "}
            {fmtInt(SENDING_DAYS)} sending days = {fmtInt(emailCap.monthly_capacity)} emails/month.
            Limits are deliverability-safe ceilings, not raw provider caps.
          </div>
          <div
            className={`mt-3 flex items-start gap-2 rounded border px-3 py-2 text-xs ${
              emailCap.sufficient
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500"
                : "border-amber-500/30 bg-amber-500/10 text-amber-500"
            }`}
          >
            {emailCap.sufficient ? (
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            ) : (
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            )}
            <span>
              {emailCap.sufficient
                ? `${fmtInt(emailCap.total_capacity)} sends over the horizon cover the ${fmtInt(emailCap.required_prospects)} prospects to contact.`
                : emailCap.message}
            </span>
          </div>
        </Card>
      )}

      {/* Experiment seeding plan (month-1 learning loop) */}
      {exp && (
        <Card className="border-card-border bg-card p-4">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            <FlaskConical className="h-3.5 w-3.5" />
            Experiment seeding plan
            <span className="ml-auto inline-flex items-center gap-2 text-[11px] font-normal normal-case tracking-normal text-muted-foreground">
              {fmtInt(exp.window_months)}-month learning window
            </span>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <CalcStat label="Experiments to run" value={fmtInt(exp.n_experiments)} />
            <CalcStat label="Leads per experiment" value={fmtInt(exp.leads_per_experiment)} />
            <CalcStat label="Total experiment leads" value={fmtInt(exp.total_experiment_leads)} />
          </div>
          {exp.hypotheses && exp.hypotheses.length > 0 && (
            <div className="mt-3">
              <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                What each experiment tests (persona × segment)
              </div>
              <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                {exp.hypotheses.map((h) => (
                  <div
                    key={h.idx}
                    className="flex items-center gap-2 rounded border border-card-border bg-background/40 px-2.5 py-1.5 text-xs"
                  >
                    <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/15 text-[10px] font-semibold text-primary">
                      {h.idx}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-foreground/90" title={h.label}>
                      {h.label}
                    </span>
                    <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                      {fmtInt(h.leads)} leads
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="mt-2 text-[11px] text-muted-foreground">{exp.rationale}</div>
          <div className="mt-3 flex items-start gap-2 rounded border border-primary/30 bg-primary/5 px-3 py-2 text-xs text-foreground/90">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
            <span>
              Run these experiments first. The winning persona/segment then drives the phased
              campaign plan — phases and seasonality are computed only after a successful
              experiment run, not here.
            </span>
          </div>
        </Card>
      )}

      {/* Will this plan hit the target? */}
      {rec && (
        <Card className="border-card-border bg-card p-4">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            <Target className="h-3.5 w-3.5" />
            Will this plan hit the target?
          </div>
          <div className="rounded border border-card-border bg-background/40 p-3">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-sm text-foreground">
              <span>{fmtInt(plan.required_prospects)} prospects</span>
              <span className="text-muted-foreground">×</span>
              <span>{convPct}%</span>
              <span className="text-muted-foreground">=</span>
              <span>{fmtInt(plan.required_closures)} deals</span>
              <span className="text-muted-foreground">×</span>
              <span>{fmtMoney(dealSize)}</span>
              <span className="text-muted-foreground">=</span>
              <span className="font-semibold text-primary">
                {fmtMoney(rec.forward_revenue_usd)}
              </span>
            </div>
            <div
              className={`mt-2 flex items-start gap-2 text-xs ${rec.reaches_target ? "text-emerald-500" : "text-amber-500"}`}
            >
              {rec.reaches_target ? (
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              ) : (
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              )}
              <span>
                {rec.reaches_target
                  ? `Executed at these assumptions, the plan reaches the ${fmtMoney(rec.target_usd)} target. The numbers are derived backwards from it, so the prospect volume is exactly what's needed to get there.`
                  : `At these assumptions the plan falls short of the ${fmtMoney(rec.target_usd)} target.`}
              </span>
            </div>
          </div>

          {rec.realistic_low_usd != null && rec.realistic_high_usd != null && (
            <div
              className={`mt-3 rounded border px-3 py-2 ${RECON_META[rec.alignment ?? "unknown"].cls}`}
            >
              <div className="text-sm font-medium">
                {RECON_META[rec.alignment ?? "unknown"].title}
              </div>
              <div className="mt-1 text-xs opacity-90">
                Market sizing puts a realistic outcome at{" "}
                {fmtMoney(rec.realistic_low_usd)}–{fmtMoney(rec.realistic_high_usd)}.
                {rec.alignment === "above_realistic" && (
                  <>
                    {" "}Your {fmtMoney(rec.target_usd)} target sits above that ceiling — the plan is
                    internally consistent, but reaching it assumes you out-perform typical market
                    capture. To plan for the realistic range instead, aim for{" "}
                    {fmtMoney(rec.realistic_low_usd)}–{fmtMoney(rec.realistic_high_usd)}, which needs
                    only ~{fmtInt(rec.prospects_for_realistic_low)}–
                    {fmtInt(rec.prospects_for_realistic_high)} prospects.
                  </>
                )}
                {rec.alignment === "within_realistic" && (
                  <>
                    {" "}Your {fmtMoney(rec.target_usd)} target sits inside that range, so the plan is
                    grounded in the market.
                  </>
                )}
                {rec.alignment === "below_realistic" && (
                  <>
                    {" "}Your {fmtMoney(rec.target_usd)} target is below that range — you may be
                    under-shooting and could safely aim higher.
                  </>
                )}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Strategic guidance */}
      {(plan.strategic_guidance ?? []).length > 0 && (
        <Card className="border-card-border bg-card p-4">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            <Lightbulb className="h-3.5 w-3.5" />
            Strategic guidance
          </div>
          <ul className="space-y-1.5 text-sm text-foreground/90">
            {plan.strategic_guidance!.map((g, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-primary">•</span>
                <span>{g}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
