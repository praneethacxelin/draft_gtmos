import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  Calculator,
  Sparkles,
  Info,
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
  type Strategy,
  type RoiVerdict,
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
    validate.mutate({
      id: strategyId,
      data: {
        investment_usd: investNum!,
        expected_revenue_usd: expectedNum!,
        timeframe_months: timeframe,
        market_segment: segment.trim() || null,
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
