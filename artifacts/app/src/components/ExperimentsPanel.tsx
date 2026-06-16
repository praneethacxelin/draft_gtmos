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
  type Experiment,
  type ExperimentBatch,
  type ExperimentParams,
} from "@/hooks/useExperiments";

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
/*  Main panel                                                        */
/* ------------------------------------------------------------------ */

export function ExperimentsPanel({ strategyId }: { strategyId: string }) {
  const { data: batches, isLoading } = useExperimentBatches(strategyId);
  const create = useCreateExperimentBatch(strategyId);
  const [n, setN] = useState(3);
  const [leads, setLeads] = useState(10);

  return (
    <div className="space-y-4">
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
            <Label className="text-xs">Leads per experiment</Label>
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
    </div>
  );
}
