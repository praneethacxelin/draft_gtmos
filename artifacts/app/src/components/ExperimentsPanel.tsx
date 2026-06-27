import { useMemo, useState } from "react";
import {
  FlaskConical,
  Play,
  Sparkles,
  Trophy,
  Loader2,
  Pencil,
  Check,
  X,
  AlertTriangle,
  Trash2,
  BarChart3,
  ChevronDown,
  ChevronRight,
  Target,
  Info,
  Rocket,
  CalendarClock,
  Users,
  Lock,
  TrendingUp,
  Send,
  Mail,
  CheckCircle2,
  Clock,
  Beaker,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ReasoningPanel } from "@/components/ReasoningPanel";
import {
  useExperimentBatches,
  useCreateExperimentBatch,
  useDeleteExperimentBatch,
  useUpdateExperiment,
  useRunExperiment,
  useRunBatch,
  useAnalyzeBatch,
  useLiveMetrics,
  usePromoteLive,
  usePromotionPreview,
  useLaunchVariant,
  useEvaluateLive,
  useSimulateWindow,
  type Experiment,
  type ExperimentBatch,
  type ExperimentParams,
  type LiveMetricsResponse,
} from "@/hooks/useExperiments";
import { useToast } from "@/hooks/use-toast";
import type { Strategy } from "@/hooks/useStrategies";
import { useCampaignPlan } from "@/hooks/useStrategies";

// The experiment batch is a relevancy TEST: each experiment samples a small,
// server-capped number of leads (≤25) to find the best Apollo params. The ROI
// plan's leads-per-experiment is the monthly OUTPUT target the winning params
// will later be scaled to, so we cap the test sample at this value.
const TEST_SAMPLE_CAP = 25;

const FACETS: { key: keyof ExperimentParams; label: string; placeholder: string }[] = [
  { key: "titles", label: "Job titles", placeholder: "VP of Support, Head of CX" },
  { key: "seniorities", label: "Seniorities", placeholder: "vp, head, director" },
  { key: "locations", label: "Locations (countries)", placeholder: "United States, India" },
  { key: "industries", label: "Industries", placeholder: "Healthcare, SaaS" },
  { key: "employee_ranges", label: "Employee ranges", placeholder: "51,200  201,1000" },
  { key: "technologies", label: "Technologies", placeholder: "Zendesk, Salesforce" },
  { key: "keywords", label: "Keywords", placeholder: "customer support, helpdesk" },
];

function toText(v?: string[]): string {
  return (v ?? []).join(", ");
}

function toArray(v: string): string[] {
  return v
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function STATUS_BADGE(status: Experiment["status"]) {
  switch (status) {
    case "done":
      return <Badge variant="secondary">Done</Badge>;
    case "running":
      return (
        <Badge variant="outline">
          <Loader2 className="mr-1 h-3 w-3 animate-spin" /> Running
        </Badge>
      );
    case "failed":
      return <Badge variant="destructive">Failed</Badge>;
    default:
      return <Badge variant="outline">Draft</Badge>;
  }
}

/* ------------------------------------------------------------------ */
/*  Editable experiment card                                          */
/* ------------------------------------------------------------------ */

function ExperimentCard({
  strategyId,
  exp,
  isBest,
  rank,
}: {
  strategyId: string;
  exp: Experiment;
  isBest: boolean;
  rank?: number;
}) {
  const [editing, setEditing] = useState(false);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [name, setName] = useState(exp.name ?? "");

  const update = useUpdateExperiment(strategyId);
  const run = useRunExperiment(strategyId);

  function startEdit() {
    const d: Record<string, string> = {};
    for (const f of FACETS) d[f.key] = toText(exp.params[f.key]);
    setDraft(d);
    setName(exp.name ?? "");
    setEditing(true);
  }

  function save() {
    const params: ExperimentParams = {};
    for (const f of FACETS) {
      const arr = toArray(draft[f.key] ?? "");
      if (arr.length) (params as Record<string, string[]>)[f.key] = arr;
    }
    update.mutate(
      { experimentId: exp.id, data: { name, params } },
      { onSuccess: () => setEditing(false) },
    );
  }

  const summary = exp.result_summary;
  const rel = exp.relevancy;

  return (
    <Card
      className={`border p-4 ${
        isBest ? "border-amber-500/50 bg-amber-500/5" : "border-card-border bg-card"
      }`}
      data-testid={`experiment-${exp.idx}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-mono text-muted-foreground">
              #{exp.idx}
            </span>
            {editing ? (
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-7 w-48 text-sm"
              />
            ) : (
              <span className="text-sm font-semibold">{exp.name}</span>
            )}
            {isBest && (
              <Badge className="gap-1 bg-amber-500 text-amber-950">
                <Trophy className="h-3 w-3" /> Best
              </Badge>
            )}
            {rank != null && !isBest && (
              <Badge variant="outline">Rank {rank}</Badge>
            )}
            {STATUS_BADGE(exp.status)}
            {exp.source === "user" && <Badge variant="outline">edited</Badge>}
            {summary?.relaxed && (
              <Badge variant="outline" className="text-amber-500">
                relaxed
              </Badge>
            )}
          </div>
          {exp.hypothesis && !editing && (
            <div className="mt-1 text-xs text-muted-foreground">{exp.hypothesis}</div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {!editing && (
            <Button
              size="sm"
              variant="ghost"
              onClick={startEdit}
              data-testid={`button-edit-experiment-${exp.idx}`}
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            size="sm"
            variant="secondary"
            disabled={run.isPending || exp.status === "running"}
            onClick={() => run.mutate(exp.id)}
            data-testid={`button-run-experiment-${exp.idx}`}
            className="gap-1"
          >
            {run.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            Run
          </Button>
        </div>
      </div>

      {/* Params: editable or read-only chips */}
      {editing ? (
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
          {FACETS.map((f) => (
            <div key={f.key}>
              <Label className="text-[11px]">{f.label}</Label>
              <Input
                value={draft[f.key] ?? ""}
                onChange={(e) => setDraft((p) => ({ ...p, [f.key]: e.target.value }))}
                placeholder={f.placeholder}
                className="mt-1 h-8 text-xs"
              />
            </div>
          ))}
          <div className="col-span-full mt-1 flex gap-2">
            <Button size="sm" onClick={save} disabled={update.isPending} className="gap-1">
              <Check className="h-3.5 w-3.5" /> Save
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)} className="gap-1">
              <X className="h-3.5 w-3.5" /> Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {FACETS.flatMap((f) =>
            (exp.params[f.key] ?? []).map((v, i) => (
              <Badge key={`${f.key}-${i}`} variant="outline" className="font-normal">
                <span className="text-muted-foreground">{f.label.split(" ")[0]}:</span>
                <span className="ml-1">{v}</span>
              </Badge>
            )),
          )}
          {FACETS.every((f) => !(exp.params[f.key] ?? []).length) && (
            <span className="text-xs text-muted-foreground">
              No parameters set — edit to add Apollo facets.
            </span>
          )}
        </div>
      )}

      {exp.error && (
        <div className="mt-3 flex items-start gap-2 rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{exp.error}</span>
        </div>
      )}

      {/* Results */}
      {exp.status === "done" && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <span className="text-muted-foreground">
              Leads:{" "}
              <span className="font-mono font-semibold text-foreground">
                {summary?.lead_count ?? exp.leads.length}
              </span>
              {rel?.requested_leads != null &&
                rel?.sample_completeness != null &&
                rel.sample_completeness < 1 && (
                  <span
                    className="ml-1 font-mono text-amber-500"
                    title={`Only returned ${summary?.lead_count ?? exp.leads.length} of the ${rel.requested_leads} requested. Partial samples are discounted vs full samples when ranking, so this can't unfairly out-rank a complete experiment.`}
                  >
                    /{rel.requested_leads} (partial)
                  </span>
                )}
            </span>
            {rel?.relevancy_score != null && (
              <span className="text-muted-foreground">
                Relevancy:{" "}
                <span className="font-mono font-semibold text-foreground">
                  {rel.relevancy_score}%
                </span>
              </span>
            )}
            {exp.score != null && (
              <span className="text-muted-foreground">
                Score:{" "}
                <span className="font-mono font-semibold text-foreground">
                  {exp.score}
                </span>
              </span>
            )}
            {summary?.winning_tier && (
              <span className="text-muted-foreground">
                Tier: <span className="text-foreground">{summary.winning_tier}</span>
              </span>
            )}
          </div>

          {rel?.summary && (
            <div className="text-xs text-muted-foreground">{rel.summary}</div>
          )}

          {(rel?.off_target_industries ?? []).length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-amber-500">Off-target:</span>
              {rel!.off_target_industries!.map((ind, i) => (
                <Badge key={i} variant="outline" className="text-amber-500">
                  {ind}
                </Badge>
              ))}
            </div>
          )}

          {exp.leads.length > 0 && (
            <div>
              <button
                type="button"
                onClick={() => setOpen((o) => !o)}
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                {open ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
                {open ? "Hide" : "Show"} {exp.leads.length} leads
              </button>
              {open && (
                <div className="mt-2 overflow-x-auto rounded border border-card-border">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/40 text-muted-foreground">
                      <tr>
                        <th className="px-2 py-1.5 font-medium">Name</th>
                        <th className="px-2 py-1.5 font-medium">Title</th>
                        <th className="px-2 py-1.5 font-medium">Company</th>
                        <th className="px-2 py-1.5 font-medium">Industry</th>
                        <th className="px-2 py-1.5 font-medium">Location</th>
                      </tr>
                    </thead>
                    <tbody>
                      {exp.leads.map((l, i) => (
                        <tr key={i} className="border-t border-card-border">
                          <td className="px-2 py-1.5">{l.name}</td>
                          <td className="px-2 py-1.5 text-muted-foreground">{l.title}</td>
                          <td className="px-2 py-1.5">{l.company}</td>
                          <td className="px-2 py-1.5 text-muted-foreground">{l.industry}</td>
                          <td className="px-2 py-1.5 text-muted-foreground">{l.location}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Batch view                                                        */
/* ------------------------------------------------------------------ */

function BatchView({
  strategyId,
  batch,
}: {
  strategyId: string;
  batch: ExperimentBatch;
}) {
  const runBatch = useRunBatch(strategyId);
  const analyze = useAnalyzeBatch(strategyId);
  const del = useDeleteExperimentBatch(strategyId);

  const experiments = batch.experiments ?? [];
  const ranById = useMemo(() => {
    const m = new Map<string, number>();
    batch.analysis?.ranking?.forEach((r) => m.set(r.experiment_id, r.rank));
    return m;
  }, [batch.analysis]);

  const anyRun = experiments.some((e) => e.status === "done");

  return (
    <Card className="border-card-border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold">{batch.name}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {experiments.length} experiments · {batch.leads_per_experiment} leads each ·{" "}
            <span className="capitalize">{batch.status}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={runBatch.isPending}
            onClick={() => runBatch.mutate(batch.id)}
            data-testid="button-run-batch"
            className="gap-1"
          >
            {runBatch.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            Run all
          </Button>
          <Button
            size="sm"
            disabled={analyze.isPending || !anyRun}
            onClick={() => analyze.mutate(batch.id)}
            data-testid="button-analyze-batch"
            className="gap-1"
            title={anyRun ? undefined : "Run at least one experiment first"}
          >
            {analyze.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <BarChart3 className="h-3.5 w-3.5" />
            )}
            Analyze
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => del.mutate(batch.id)}
            disabled={del.isPending}
            data-testid="button-delete-batch"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {(runBatch.isError || analyze.isError) && (
        <div className="mt-3 flex items-start gap-2 rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            {((runBatch.error || analyze.error) as Error)?.message ?? "Action failed"}
          </span>
        </div>
      )}

      {/* Analysis summary */}
      {batch.analysis && (
        <div className="mt-4 space-y-3">
          <ReasoningPanel provenance={batch.analysis._provenance} />
          <Card className="border-amber-500/30 bg-amber-500/5 p-4">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-amber-500">
              <Trophy className="h-4 w-4" /> Best performing experiment
            </div>
            {batch.analysis.why_best && (
              <div className="text-sm text-foreground/90">{batch.analysis.why_best}</div>
            )}
            {batch.analysis.winning_parameters_insight && (
              <div className="mt-2 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">What drove it: </span>
                {batch.analysis.winning_parameters_insight}
              </div>
            )}
            {(batch.analysis.recommendations ?? []).length > 0 && (
              <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                {batch.analysis.recommendations!.map((r, i) => (
                  <li key={i} className="flex gap-2">
                    <span>•</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}

      {/* Live (closed-loop) funnel test */}
      {batch.status === "analyzed" && (
        <LiveExperimentSection strategyId={strategyId} batch={batch} />
      )}

      {/* Experiment cards */}
      <div className="mt-4 space-y-3">
        {experiments.map((e) => (
          <ExperimentCard
            key={e.id}
            strategyId={strategyId}
            exp={e}
            isBest={batch.best_experiment_id === e.id}
            rank={ranById.get(e.id)}
          />
        ))}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Live (closed-loop) funnel test                                    */
/* ------------------------------------------------------------------ */

const LIVE_STAGE_COPY: Record<string, { label: string; tone: string }> = {
  drafted: { label: "Drafted — ready to send", tone: "text-amber-500" },
  running: { label: "Live window open", tone: "text-emerald-500" },
  completed: { label: "Window closed", tone: "text-primary" },
};

function pct(n?: number): string {
  return `${(n ?? 0).toFixed(0)}%`;
}

function LiveExperimentSection({
  strategyId,
  batch,
}: {
  strategyId: string;
  batch: ExperimentBatch;
}) {
  const { toast } = useToast();
  const live = batch.live_status ?? null;
  const promote = usePromoteLive(strategyId);
  const launch = useLaunchVariant(strategyId);
  const evaluate = useEvaluateLive(strategyId);
  const simulate = useSimulateWindow(strategyId);
  const [promoteCount, setPromoteCount] = useState(batch.leads_per_experiment ?? 5);
  const preview = usePromotionPreview(
    strategyId,
    batch.id,
    promoteCount,
    !live || live === "drafted",
  );
  const { data: metrics } = useLiveMetrics(
    strategyId,
    batch.id,
    live === "running" || live === "completed",
  );

  const experiments = batch.experiments ?? [];
  const winnerId = batch.live_winner_experiment_id ?? batch.live_analysis?.winner_experiment_id;
  const metricByExp = useMemo(() => {
    const m = new Map<string, LiveMetricsResponse["variants"][number]>();
    (metrics?.variants ?? []).forEach((v) => m.set(v.experiment_id, v));
    return m;
  }, [metrics]);

  function onPromote() {
    promote.mutate(
      { batchId: batch.id, draftPerVariant: promoteCount },
      {
        onSuccess: (r: any) => {
          const skipped = (r.skipped ?? []) as Array<{ name: string; reason: string }>;
          toast({
            title: "Promoted to live test",
            description:
              `${r.total_cohort ?? 0} leads across ${(r.variants ?? []).length} variant(s) moved forward · ` +
              `${r.total_drafted ?? 0} sequences drafted (scaled by rank, up to ${r.per_variant_budget ?? promoteCount}/variant).` +
              (skipped.length
                ? ` Skipped ${skipped.length} low-fit: ${skipped.map((s) => `${s.name} (${s.reason})`).join(", ")}.`
                : ""),
          });
        },
        onError: (e: any) =>
          toast({ title: "Promote failed", description: String(e?.message ?? e), variant: "destructive" }),
      },
    );
  }

  function onLaunch(expId: string, name?: string) {
    launch.mutate(expId, {
      onSuccess: (r: any) =>
        toast({
          title: `Launched ${name ?? "variant"}`,
          description: `${r.launched ?? 0} sent · ${r.skipped ?? 0} skipped. Live window ${r.window_ends_at ? `ends ${new Date(r.window_ends_at).toLocaleDateString()}` : "open"}.`,
        }),
      onError: (e: any) =>
        toast({ title: "Launch failed", description: String(e?.message ?? e), variant: "destructive" }),
    });
  }

  function onEvaluate() {
    evaluate.mutate(batch.id, {
      onSuccess: (r: any) =>
        toast(
          r?.pending
            ? { title: "Window still open", description: r.reason }
            : { title: "Live winner picked", description: r?.analysis?.winner_name ?? "No positive replies yet." },
        ),
      onError: (e: any) =>
        toast({ title: "Evaluate failed", description: String(e?.message ?? e), variant: "destructive" }),
    });
  }

  function onSimulate() {
    simulate.mutate(batch.id, {
      onSuccess: (r: any) =>
        toast({
          title: "Simulated full window",
          description: `Winner: ${r?.analysis?.winner_name ?? "none"}. Funnel + replies synthesized so you can see the loop close.`,
        }),
      onError: (e: any) =>
        toast({ title: "Simulate failed", description: String(e?.message ?? e), variant: "destructive" }),
    });
  }

  const windowEnds = batch.window_ends_at ? new Date(batch.window_ends_at) : null;

  return (
    <div className="mt-5 rounded-lg border border-primary/30 bg-primary/5 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Beaker className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">Live funnel test</span>
          {live && (
            <Badge variant="secondary" className={`text-[10px] ${LIVE_STAGE_COPY[live]?.tone ?? ""}`}>
              {LIVE_STAGE_COPY[live]?.label ?? live}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {(!live || live === "drafted") && (
            <label className="flex items-center gap-1 text-xs text-muted-foreground" title="Per-variant lead budget for the funnel test. The top-ranked (winner) variant promotes its full cohort up to this number; lower ranks promote proportionally fewer (by composite score). Defaults to your leads-per-experiment.">
              <span>Leads / variant</span>
              <Input
                type="number"
                min={1}
                max={25}
                value={promoteCount}
                onChange={(e) =>
                  setPromoteCount(Math.max(1, Math.min(25, Number(e.target.value) || 1)))
                }
                className="h-7 w-16"
              />
            </label>
          )}
          {!live && (
            <Button size="sm" onClick={onPromote} disabled={promote.isPending}>
              {promote.isPending ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <FlaskConical className="mr-2 h-3.5 w-3.5" />}
              Promote to live test
            </Button>
          )}
          {live === "drafted" && (
            <Button size="sm" variant="outline" onClick={onPromote} disabled={promote.isPending}>
              {promote.isPending ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Pencil className="mr-2 h-3.5 w-3.5" />}
              Top up drafts
            </Button>
          )}
          {live === "running" && (
            <Button size="sm" variant="outline" onClick={onEvaluate} disabled={evaluate.isPending}>
              {evaluate.isPending ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Trophy className="mr-2 h-3.5 w-3.5" />}
              Evaluate window
            </Button>
          )}
          {(live === "drafted" || live === "running") && (
            <Button
              size="sm"
              variant="ghost"
              className="text-muted-foreground"
              title="Test only: synthesize sends + replies + meetings so the loop closes immediately"
              onClick={onSimulate}
              disabled={simulate.isPending}
            >
              {simulate.isPending ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Clock className="mr-2 h-3.5 w-3.5" />}
              Simulate window
            </Button>
          )}
        </div>
      </div>

      <p className="mt-2 text-xs text-muted-foreground">
        Promotes each variant into a real contact cohort with drafted sequences (no auto-send). You
        launch each variant, then over the{" "}
        {batch.window_months ?? 1}-month window the winner is the one with the highest{" "}
        <span className="font-medium text-foreground">positive-intent reply rate</span> — replies
        that book a call/meeting to move the deal forward.
        {windowEnds && live === "running" && (
          <> Window ends <span className="font-medium text-foreground">{windowEnds.toLocaleDateString()}</span>.</>
        )}
      </p>

      {(!live || live === "drafted") && preview.data && (
        <div className="mt-3 rounded border border-primary/30 bg-background/60 p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase tracking-widest text-primary">
              Moving forward to the funnel test
            </div>
            <div className="text-sm font-semibold text-foreground">
              {preview.data.total_to_promote}
              <span className="text-xs font-normal text-muted-foreground">
                {" "}/ {preview.data.total_available} leads
              </span>
            </div>
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Each variant promotes a share of its leads scaled by rank (composite score), up to{" "}
            {preview.data.budget_per_variant}/variant. The winner promotes its full cohort.
          </p>
          <div className="mt-2 space-y-1">
            {preview.data.variants.map((v) => (
              <div
                key={v.experiment_id}
                className="flex items-center justify-between gap-2 text-xs"
              >
                <div className="flex min-w-0 items-center gap-1.5">
                  {v.is_winner && <Trophy className="h-3 w-3 shrink-0 text-amber-500" />}
                  <span className="truncate text-foreground">{v.name ?? `Variant ${v.idx + 1}`}</span>
                  {v.skipped && (
                    <Badge variant="outline" className="shrink-0 text-[9px] text-muted-foreground">
                      skipped
                    </Badge>
                  )}
                </div>
                {v.skipped ? (
                  <span className="shrink-0 text-[10px] text-muted-foreground">{v.reason}</span>
                ) : (
                  <span className="shrink-0 font-medium text-foreground">
                    {v.planned}
                    <span className="font-normal text-muted-foreground">
                      {" "}of {v.available_leads}
                    </span>
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {live === "completed" && batch.live_analysis && (
        <div className="mt-3 rounded border border-primary/30 bg-background/60 p-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-primary">
            <Trophy className="h-3.5 w-3.5" /> Live winner
          </div>
          <div className="mt-1 text-sm text-foreground">
            {batch.live_analysis.any_positive
              ? batch.live_analysis.winner_name
              : "No variant booked a meeting in the window yet."}
          </div>
          {(batch.live_analysis.recommendations ?? []).length > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
              {batch.live_analysis.recommendations!.map((r, i) => (
                <li key={i} className="flex gap-2"><span>•</span><span>{r}</span></li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Per-variant funnel rows */}
      {live && (
        <div className="mt-3 space-y-2">
          {experiments.map((e) => {
            const m = metricByExp.get(e.id);
            const isWinner = winnerId === e.id;
            const launched = m?.launched ?? !!e.live_launched_at;
            return (
              <div
                key={e.id}
                className={`rounded border p-2.5 ${isWinner ? "border-primary bg-primary/10" : "border-card-border bg-background/50"}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {isWinner && <Trophy className="h-3.5 w-3.5 text-primary" />}
                    <span className="text-sm font-medium">{e.name}</span>
                    <span className="text-xs text-muted-foreground">
                      cohort {e.cohort_size ?? m?.cohort_size ?? 0}
                    </span>
                  </div>
                  {live === "running" && !launched && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onLaunch(e.id, e.name)}
                      disabled={launch.isPending}
                    >
                      <Send className="mr-2 h-3.5 w-3.5" /> Launch send
                    </Button>
                  )}
                  {live === "drafted" && (
                    <Button
                      size="sm"
                      onClick={() => onLaunch(e.id, e.name)}
                      disabled={launch.isPending}
                    >
                      <Send className="mr-2 h-3.5 w-3.5" /> Launch send
                    </Button>
                  )}
                  {launched && (
                    <Badge variant="secondary" className="text-[10px] text-emerald-500">
                      <CheckCircle2 className="mr-1 h-3 w-3" /> Sent
                    </Badge>
                  )}
                </div>
                {m && (
                  <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-5">
                    <FunnelStat icon={<Mail className="h-3 w-3" />} label="Contacted" value={`${m.contacted}`} />
                    <FunnelStat icon={<TrendingUp className="h-3 w-3" />} label="Replied" value={`${m.replied}`} sub={pct(m.reply_rate_pct)} />
                    <FunnelStat icon={<Users className="h-3 w-3" />} label="Interested" value={`${m.interested}`} />
                    <FunnelStat icon={<CalendarClock className="h-3 w-3" />} label="Meetings" value={`${m.positive}`} />
                    <FunnelStat icon={<Trophy className="h-3 w-3" />} label="Positive rate" value={pct(m.positive_rate_pct)} highlight />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function FunnelStat({
  icon,
  label,
  value,
  sub,
  highlight,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  highlight?: boolean;
}) {
  return (
    <div className={`rounded border p-1.5 ${highlight ? "border-primary/40 bg-primary/5" : "border-card-border bg-background/40"}`}>
      <div className="flex items-center gap-1 text-[9px] font-medium uppercase tracking-widest text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-0.5 font-mono text-sm font-semibold text-foreground">
        {value}
        {sub && <span className="ml-1 text-[10px] font-normal text-muted-foreground">{sub}</span>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Campaign execution plan (post-experiments)                        */
/* ------------------------------------------------------------------ */

function fmtUsd(n?: number | null): string {
  if (n == null) return "—";
  return `$${Math.round(n).toLocaleString()}`;
}

function Stat({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded border border-card-border bg-background/50 p-2.5">
      <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-1 font-mono text-sm font-semibold text-foreground">
        {value}
      </div>
      {sub && <div className="text-[10px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

function CampaignPlanSection({ strategyId }: { strategyId: string }) {
  const { data: plan, isLoading } = useCampaignPlan(strategyId);

  if (isLoading) {
    return (
      <Card className="border-card-border bg-card p-5">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading campaign plan…
        </div>
      </Card>
    );
  }
  if (!plan) return null;

  if (!plan.ready) {
    return (
      <Card className="border-card-border bg-muted/30 p-5">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 rounded bg-muted p-1.5 text-muted-foreground">
            <Lock className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold text-foreground">
              Campaign execution plan — locked
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{plan.reason}</p>
          </div>
        </div>
      </Card>
    );
  }

  const phases = plan.phases ?? [];
  const facetEntries = Object.entries(plan.winning_facets ?? {});

  return (
    <Card className="border-primary/30 bg-primary/5 p-5">
      <div className="mb-1 flex items-center gap-2">
        <Rocket className="h-4 w-4 text-primary" />
        <div className="text-sm font-semibold">Campaign execution plan</div>
        {plan.overall_confidence && (
          <Badge variant="secondary" className="ml-auto text-[10px]">
            {plan.overall_confidence} confidence
          </Badge>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        Unlocked by the winning experiment
        {plan.winning_experiment_name ? ` “${plan.winning_experiment_name}”` : ""}. Built from
        the ROI phased targets, front-loaded, and split by persona.
      </p>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat
          icon={<CalendarClock className="h-3.5 w-3.5" />}
          label="Kickoff"
          value={plan.kickoff_label ?? "—"}
          sub={`after ${plan.experiment_window_months ?? 1}-mo window`}
        />
        <Stat
          icon={<Users className="h-3.5 w-3.5" />}
          label="Total prospects"
          value={(plan.total_prospects ?? 0).toLocaleString()}
        />
        <Stat
          icon={<TrendingUp className="h-3.5 w-3.5" />}
          label="Front-loaded"
          value={`${plan.frontload_first_two_pct ?? 0}%`}
          sub="in first 2 phases"
        />
        <Stat
          icon={<Target className="h-3.5 w-3.5" />}
          label="Annual target"
          value={fmtUsd(plan.annual_target_usd)}
        />
      </div>

      {facetEntries.length > 0 && (
        <div className="mt-4 rounded border border-card-border bg-background/50 p-3">
          <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            <Trophy className="h-3.5 w-3.5" /> Winning targeting facets
          </div>
          <div className="flex flex-wrap gap-1.5">
            {facetEntries.flatMap(([key, val]) => {
              const items = Array.isArray(val) ? val : [val];
              return items.map((v, i) => (
                <span
                  key={`${key}-${i}`}
                  className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-foreground/80"
                >
                  {v}
                </span>
              ));
            })}
          </div>
          {plan.winning_parameters_insight && (
            <p className="mt-2 text-[11px] text-muted-foreground">
              {plan.winning_parameters_insight}
            </p>
          )}
        </div>
      )}

      <div className="mt-4 space-y-2">
        {phases.map((ph) => (
          <div
            key={ph.phase}
            className="rounded border border-card-border bg-background/40 p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-foreground">{ph.label}</span>
              <span className="text-[11px] text-muted-foreground">
                {ph.calendar_range} · {ph.quarter}
              </span>
              <span className="ml-auto font-mono text-sm font-semibold text-primary">
                {ph.prospect_count.toLocaleString()} prospects
              </span>
              <span className="font-mono text-[11px] text-muted-foreground">
                {ph.prospect_share_pct}% share
              </span>
            </div>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
              <span>Target {fmtUsd(ph.revenue_target_usd)}</span>
              {ph.carried_in_usd != null && ph.carried_in_usd > 0 && (
                <span className="text-amber-400" title="Revenue carried forward from an earlier phase that fell short due to seasonality">
                  +{fmtUsd(ph.carried_in_usd)} carried in → {fmtUsd(ph.effective_target_usd ?? ph.revenue_target_usd)} effective
                </span>
              )}
              {ph.carry_forward_usd != null && ph.carry_forward_usd > 0 && (
                <span className="text-amber-400" title="Seasonal shortfall rolled into the next phase">
                  {fmtUsd(ph.carry_forward_usd)} carried forward
                </span>
              )}
              <span>{ph.required_closures} closures</span>
              {ph.season_factor != null && (
                <span title="Seasonality multiplier for this phase's calendar window">
                  ×{ph.season_factor.toFixed(2)} season
                </span>
              )}
              {ph.projected_attainment_pct != null && (
                <span
                  className={
                    ph.projected_attainment_pct >= 99
                      ? undefined
                      : "text-amber-400"
                  }
                  title="Projected target attainment after seasonality and capacity"
                >
                  {Math.round(ph.projected_attainment_pct)}% projected attainment
                </span>
              )}
              {ph.confidence && <span>{ph.confidence} confidence</span>}
            </div>
            {ph.persona_split.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {ph.persona_split.map((p) => (
                  <span
                    key={p.persona_type}
                    className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary"
                  >
                    {p.label} {p.weight_pct}% · {p.prospect_count.toLocaleString()}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {(plan.notes ?? []).map((note, i) => (
        <div
          key={i}
          className="mt-2 flex items-start gap-2 text-[11px] text-muted-foreground"
        >
          <Info className="mt-0.5 h-3 w-3 shrink-0" />
          <span>{note}</span>
        </div>
      ))}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Main panel                                                        */
/* ------------------------------------------------------------------ */

export function ExperimentsPanel({
  strategyId,
  strategy,
}: {  strategyId: string;
  strategy?: Strategy | null;
}) {
  const { data: batches, isLoading } = useExperimentBatches(strategyId);
  const create = useCreateExperimentBatch(strategyId);

  // Seeding plan recommended by the ROI calculator (capacity-driven).
  const roiPlan = strategy?.roi?.gtm_plan?.experiment_plan;
  const recExperiments = roiPlan?.n_experiments
    ? Math.max(1, Math.min(12, roiPlan.n_experiments))
    : null;
  const recTargetLeads = roiPlan?.leads_per_experiment ?? null;
  const recSampleLeads =
    recTargetLeads != null ? Math.max(1, Math.min(TEST_SAMPLE_CAP, recTargetLeads)) : null;

  const [n, setN] = useState(recExperiments ?? 3);
  const [leads, setLeads] = useState(recSampleLeads ?? 10);

  function applyRoiPlan() {
    if (recExperiments != null) setN(recExperiments);
    if (recSampleLeads != null) setLeads(recSampleLeads);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <div className="rounded-md bg-primary/10 p-2 text-primary">
          <FlaskConical className="h-4 w-4" />
        </div>
        <div>
          <p className="text-sm font-semibold">Experiments</p>
          <p className="text-sm text-muted-foreground">
            A real learning loop: each variant first tests a small sample across Apollo targeting
            facets to find the highest-fit leads, then runs a live funnel test — send, reply, meeting —
            over a window. The winner is the variant with the highest positive-intent reply rate
            (replies that book a call/meeting), and only it is scaled into Prospects.
          </p>
        </div>
      </div>

      <ReasoningPanel
        fallback={{
          source: "ai_generated",
          logic:
            "The GTM engineer picks how many experiments to run. The AI seeds that many distinct Apollo parameter sets (location, industry, size, titles, tech) from the profile's ICP. Each is editable, runs against Apollo, and the batch is analysed to surface the best parameter set and the most relevant leads.",
          steps: [
            "Pick N experiments + leads each",
            "AI seeds distinct Apollo facet combinations",
            "Edit any facet, then run each (or all) against Apollo",
            "Analyse: score relevancy vs product, rank, pick the best",
          ],
        }}
      />

      <Card className="border-card-border bg-card p-5">
        <div className="mb-3 flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-primary" />
          <div className="text-sm font-semibold">New experiment batch</div>
        </div>
        {roiPlan && recExperiments != null && (
          <div className="mb-4 rounded border border-primary/30 bg-primary/5 p-3">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-primary">
              <Target className="h-3.5 w-3.5" />
              ROI-recommended seeding plan
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-1 text-sm text-foreground">
              <span>
                <span className="font-mono font-semibold">{recExperiments}</span> experiment
                {recExperiments === 1 ? "" : "s"}
              </span>
              {recSampleLeads != null && (
                <span>
                  <span className="font-mono font-semibold">{recSampleLeads}</span> test leads /
                  experiment
                </span>
              )}
              {recTargetLeads != null &&
                recSampleLeads != null &&
                recTargetLeads > recSampleLeads && (
                  <span className="text-muted-foreground">
                    → scale winners to{" "}
                    <span className="font-mono font-semibold text-foreground">
                      {recTargetLeads.toLocaleString()}
                    </span>{" "}
                    / month
                  </span>
                )}
              {roiPlan.window_months != null && (
                <span className="text-muted-foreground">
                  {roiPlan.window_months}-month learning window
                </span>
              )}
            </div>
            <div className="mt-2 flex items-start gap-2 text-[11px] text-muted-foreground">
              <Info className="mt-0.5 h-3 w-3 shrink-0" />
              <span>
                Each experiment first runs a small relevancy test (sample capped at{" "}
                {TEST_SAMPLE_CAP} leads) to find the best Apollo params. The{" "}
                {recTargetLeads != null ? recTargetLeads.toLocaleString() : "target"} leads/month is
                the output you scale the winning params to after a successful run.
              </span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={applyRoiPlan}
              className="mt-3 gap-2"
              data-testid="button-apply-roi-plan"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Apply ROI plan
            </Button>
          </div>
        )}
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label className="text-xs">Number of experiments</Label>
            <Input
              type="number"
              min={1}
              max={12}
              value={n}
              onChange={(e) => setN(Math.max(1, Math.min(12, Number(e.target.value) || 1)))}
              className="mt-1 h-9 w-32"
              data-testid="input-experiment-count"
            />
          </div>
          <div>
            <Label className="text-xs">Test leads per experiment</Label>
            <Input
              type="number"
              min={1}
              max={25}
              value={leads}
              onChange={(e) => setLeads(Math.max(1, Math.min(25, Number(e.target.value) || 1)))}
              className="mt-1 h-9 w-32"
              data-testid="input-experiment-leads"
            />
          </div>
          <Button
            onClick={() => create.mutate({ n, leads_per_experiment: leads })}
            disabled={create.isPending}
            data-testid="button-create-batch"
            className="gap-2"
          >
            {create.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Seed experiments
          </Button>
        </div>
        {create.isError && (
          <div className="mt-3 flex items-start gap-2 rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{(create.error as Error)?.message ?? "Failed to seed experiments"}</span>
          </div>
        )}
      </Card>

      {isLoading ? (
        <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading experiments…
        </div>
      ) : (batches ?? []).length === 0 ? (
        <div className="rounded border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          No experiments yet. Seed a batch above to start finding the best Apollo
          parameters for this product.
        </div>
      ) : (
        <div className="space-y-4">
          {batches!.map((b) => (
            <BatchView key={b.id} strategyId={strategyId} batch={b} />
          ))}
        </div>
      )}

      <CampaignPlanSection strategyId={strategyId} />
    </div>
  );
}
