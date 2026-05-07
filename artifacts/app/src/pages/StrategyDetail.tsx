import { useEffect, useState } from "react";
import { useRoute } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/Pills";
import {
  useStrategy,
  useMarketSizing,
  useCompetitors,
  useRunCompetitors,
  usePatterns,
  useRunPatterns,
  strategyKeys,
  type Icp,
  type Persona,
  type PersonaMatrix,
  type ProblemRow,
  type NaicsSegment,
  type StakeholderMap,
  type UseCase,
} from "@/hooks/useStrategies";
import { StakeholderFlow } from "@/components/StakeholderFlow";
import { apiUrl } from "@/lib/api";
import { fmtUsd } from "@/lib/format";
import {
  Check,
  Loader2,
  CircleDot,
  PlayCircle,
  TrendingUp,
  Sparkles,
  Crosshair,
} from "lucide-react";

const STAGES = [
  { key: "icp", label: "ICP modeling" },
  { key: "personas", label: "Persona matrix" },
  { key: "problems", label: "Problem map" },
  { key: "naics", label: "NAICS segmentation" },
  { key: "stakeholders", label: "Stakeholder graph" },
  { key: "use_cases", label: "Use case library" },
];

export function StrategyDetail() {
  const [, params] = useRoute("/strategy/:id");
  const id = params?.id;
  const { data: strategy, isLoading } = useStrategy(id);
  const qc = useQueryClient();
  const [streaming, setStreaming] = useState(false);
  const [stageStatus, setStageStatus] = useState<Record<string, string>>({});
  const sizing = useMarketSizing();
  const runComps = useRunCompetitors();
  const { data: competitors } = useCompetitors(id);
  const { data: patterns } = usePatterns(id);
  const runPatterns = useRunPatterns();

  useEffect(() => {
    if (!strategy || strategy.status === "ready" || streaming) return;
    // auto-run if draft
  }, [strategy, streaming]);

  function startStream() {
    if (!id) return;
    setStreaming(true);
    setStageStatus({});
    const es = new EventSource(apiUrl(`/api/strategies/${id}/run`));
    const handle = (stage: string, status: string) =>
      setStageStatus((prev) => ({ ...prev, [stage]: status }));

    es.addEventListener("stage_start", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        handle(data.stage, "active");
      } catch {}
    });
    es.addEventListener("stage_complete", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        handle(data.stage, "done");
        qc.invalidateQueries({ queryKey: strategyKeys.detail(id) });
      } catch {}
    });
    es.addEventListener("complete", () => {
      es.close();
      setStreaming(false);
      qc.invalidateQueries({ queryKey: strategyKeys.detail(id) });
      qc.invalidateQueries({ queryKey: strategyKeys.list });
    });
    es.addEventListener("error", () => {
      es.close();
      setStreaming(false);
    });
  }

  if (isLoading || !strategy) {
    return <Skeleton className="h-64 w-full" />;
  }

  const ready = strategy.status === "ready";

  return (
    <>
      <PageHeader
        eyebrow="Stage 1 · Strategy"
        title={strategy.product_name}
        subtitle={strategy.description}
        actions={
          <div className="flex items-center gap-2">
            <StatusPill status={strategy.status} />
            {!streaming && (
              <Button onClick={startStream} data-testid="button-run-s1">
                <PlayCircle className="mr-2 h-4 w-4" />
                {ready ? "Re-run S1" : "Run S1"}
              </Button>
            )}
          </div>
        }
      />

      {(streaming || Object.keys(stageStatus).length > 0) && (
        <Card className="mb-6 border-card-border bg-card p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="h-4 w-4 text-primary" /> Live agent pipeline
          </div>
          <div className="space-y-2">
            {STAGES.map((s) => {
              const status = stageStatus[s.key];
              return (
                <div
                  key={s.key}
                  className="flex items-center gap-3 rounded border border-border bg-background/40 p-3"
                >
                  {status === "done" ? (
                    <Check className="h-4 w-4 text-primary" />
                  ) : status === "active" ? (
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  ) : (
                    <CircleDot className="h-4 w-4 text-muted-foreground" />
                  )}
                  <div className="text-sm">{s.label}</div>
                  <div className="ml-auto text-[10px] uppercase tracking-widest text-muted-foreground">
                    {status ?? "queued"}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      <Tabs defaultValue="icp" className="space-y-4">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="icp" data-testid="tab-icp">ICP</TabsTrigger>
          <TabsTrigger value="personas">Personas</TabsTrigger>
          <TabsTrigger value="problems">Problems</TabsTrigger>
          <TabsTrigger value="naics">NAICS</TabsTrigger>
          <TabsTrigger value="stakeholders">Stakeholders</TabsTrigger>
          <TabsTrigger value="use_cases">Use cases</TabsTrigger>
          <TabsTrigger value="market">Market sizing</TabsTrigger>
          <TabsTrigger value="competitors">Competitors</TabsTrigger>
          <TabsTrigger value="patterns">Patterns</TabsTrigger>
        </TabsList>

        <TabsContent value="icp">
          <IcpView icp={strategy.icp} />
        </TabsContent>
        <TabsContent value="personas">
          <PersonasView personas={strategy.personas} />
        </TabsContent>
        <TabsContent value="problems">
          <ProblemsView problems={strategy.problems} />
        </TabsContent>
        <TabsContent value="naics">
          <NaicsView naics={strategy.naics} />
        </TabsContent>
        <TabsContent value="stakeholders">
          <StakeholderGraph map={strategy.stakeholder_map} />
        </TabsContent>
        <TabsContent value="use_cases">
          <UseCasesView use_cases={strategy.use_cases} />
        </TabsContent>

        <TabsContent value="market">
          <Card className="border-card-border bg-card p-5">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-sm font-semibold">TAM / SAM / SOM</div>
              <Button
                size="sm"
                variant="secondary"
                disabled={sizing.isPending}
                onClick={() => id && sizing.mutate(id)}
                data-testid="button-market-sizing"
              >
                {sizing.isPending ? "Sizing…" : "Recompute"}
              </Button>
            </div>
            {strategy.tam_sam_som ? (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {(["tam", "sam", "som"] as const).map((k) => {
                  const v = strategy.tam_sam_som?.[k];
                  return (
                    <div key={k} className="rounded border border-border p-4">
                      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                        {k}
                      </div>
                      <div className="mt-2 font-mono text-2xl tabular-nums">
                        {v?.label ?? fmtUsd(v?.value_usd)}
                      </div>
                    </div>
                  );
                })}
                <div className="md:col-span-3 rounded border border-border bg-background/40 p-3 text-xs text-muted-foreground">
                  <div>
                    Methodology: {strategy.tam_sam_som.methodology ?? "—"}
                  </div>
                  <div className="mt-1">
                    Confidence: {strategy.tam_sam_som.confidence ?? "—"} ·{" "}
                    {strategy.tam_sam_som.uses_live_data ? "Live data via SerpAPI" : "AI estimate"}
                  </div>
                </div>
              </div>
            ) : (
              <Empty label="No market sizing computed yet." />
            )}
          </Card>
        </TabsContent>

        <TabsContent value="competitors">
          <Card className="border-card-border bg-card p-5">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-sm font-semibold">Competitor landscape</div>
              <Button
                size="sm"
                variant="secondary"
                disabled={runComps.isPending}
                onClick={() => id && runComps.mutate(id)}
                data-testid="button-run-competitors"
              >
                {runComps.isPending ? "Researching…" : "Run research"}
              </Button>
            </div>
            <div className="space-y-2">
              {competitors?.map((c) => (
                <div
                  key={c.id}
                  className="rounded border border-border bg-background/40 p-3"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium">
                        {c.name}
                        {c.website && (
                          <span className="ml-2 text-xs text-muted-foreground">
                            {c.website}
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {c.positioning}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-sm tabular-nums">
                        {c.g2_rating?.toFixed(1) ?? "—"}
                      </div>
                      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                        G2
                      </div>
                    </div>
                  </div>
                  {c.weaknesses && c.weaknesses.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {c.weaknesses.map((w, i) => (
                        <span
                          key={i}
                          className="rounded bg-destructive/10 px-1.5 py-0.5 text-[10px] text-destructive"
                        >
                          {w}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {(!competitors || competitors.length === 0) && (
                <Empty label="No competitor research yet. Run to generate." />
              )}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="patterns">
          <Card className="border-card-border bg-card p-5">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-sm font-semibold">Pattern recognition</div>
              <Button
                size="sm"
                variant="secondary"
                disabled={runPatterns.isPending}
                onClick={() => id && runPatterns.mutate(id)}
                data-testid="button-run-patterns"
              >
                {runPatterns.isPending ? "Clustering…" : "Recognize patterns"}
              </Button>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {patterns?.map((p) => (
                <div
                  key={p.id}
                  className="rounded border border-border bg-background/40 p-3"
                >
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Crosshair className="h-4 w-4 text-primary" />
                    {p.pattern_name}
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      {(p.signal_combination ?? []).join(" + ")}
                    </span>
                    <span className="font-mono tabular-nums text-foreground">
                      {(p.conversion_rate * 100).toFixed(0)}% conv
                    </span>
                  </div>
                </div>
              ))}
              {(!patterns || patterns.length === 0) && (
                <Empty label="No clusters yet. Run signals first, then recognize patterns." />
              )}
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="rounded border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
      {label}
    </div>
  );
}

function IcpView({ icp }: { icp?: Icp | null }) {
  if (!icp) return <Empty label="ICP not generated yet." />;
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Card className="border-card-border bg-card p-5">
        <div className="text-sm font-semibold">Firmographics</div>
        <dl className="mt-3 space-y-2 text-sm">
          <Field k="Industries" v={(icp.industries ?? []).join(", ")} />
          <Field k="Employee size" v={icp.employee_size_range} />
          <Field k="Revenue" v={icp.revenue_range} />
          <Field k="Geographies" v={(icp.geographies ?? []).join(", ")} />
          <Field
            k="Tech signals"
            v={(icp.tech_stack_signals ?? []).join(", ")}
          />
        </dl>
      </Card>
      <Card className="border-card-border bg-card p-5">
        <div className="text-sm font-semibold">Segments</div>
        <div className="mt-3 space-y-2">
          {(icp.segments ?? []).map((s, i) => (
            <div
              key={i}
              className="rounded border border-border bg-background/40 p-3"
            >
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">{s.name}</div>
                <div className="font-mono text-xs tabular-nums text-primary">
                  {s.fit_score}
                </div>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {s.rationale}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Field({ k, v }: { k: string; v?: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-xs uppercase tracking-widest text-muted-foreground">
        {k}
      </dt>
      <dd className="text-right text-foreground">{v || "—"}</dd>
    </div>
  );
}

function PersonasView({ personas }: { personas?: PersonaMatrix | null }) {
  if (!personas) return <Empty label="Personas not generated yet." />;
  const types: { key: string; label: string }[] = [
    { key: "champion", label: "Champion" },
    { key: "economic_buyer", label: "Economic buyer" },
    { key: "blocker", label: "Blocker" },
  ];
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {types.map(({ key, label }) => {
        const p = (personas as Record<string, Persona | undefined>)[key];
        if (!p) return null;
        return (
          <Card key={key} className="border-card-border bg-card p-5">
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
              {label}
            </div>
            <div className="mt-1 text-base font-semibold">{p.title}</div>
            <Section label="Goals" items={p.goals} />
            <Section label="Frustrations" items={p.frustrations} />
            <Section label="Objections" items={p.objections} />
            {p.communication_style && (
              <div className="mt-3 text-xs italic text-muted-foreground">
                Communication: {p.communication_style}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

function Section({ label, items }: { label: string; items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mt-3">
      <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <ul className="mt-1 space-y-1 text-xs text-foreground">
        {items.map((x, i) => (
          <li key={i} className="flex gap-2">
            <span className="text-primary">›</span>
            {x}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProblemsView({ problems }: { problems?: { problems?: ProblemRow[] } | null }) {
  const list = problems?.problems ?? [];
  if (list.length === 0) return <Empty label="Problem map not generated yet." />;
  return (
    <Card className="border-card-border bg-card p-0">
      <div className="divide-y divide-border">
        {list.map((p, i) => (
          <div key={i} className="grid grid-cols-12 gap-4 p-4">
            <div className="col-span-2 text-xs uppercase tracking-widest text-muted-foreground">
              {p.persona}
            </div>
            <div className="col-span-7">
              <div className="text-sm font-medium">{p.pain}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                Trigger: {p.trigger}
              </div>
              <div className="text-xs text-muted-foreground">
                Angle: {p.product_angle}
              </div>
            </div>
            <div className="col-span-3 text-right">
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-widest ${
                  p.urgency === "high"
                    ? "bg-destructive/15 text-destructive"
                    : p.urgency === "medium"
                      ? "bg-amber-500/15 text-amber-400"
                      : "bg-muted text-muted-foreground"
                }`}
              >
                {p.urgency} urgency
              </span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function NaicsView({ naics }: { naics?: { segments?: NaicsSegment[] } | null }) {
  const segs = naics?.segments ?? [];
  if (segs.length === 0) return <Empty label="NAICS segmentation not generated yet." />;
  return (
    <Card className="border-card-border bg-card p-0 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted/40">
          <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
            <th className="px-4 py-2">Code</th>
            <th className="px-4 py-2">Industry</th>
            <th className="px-4 py-2">Sub-vertical</th>
            <th className="px-4 py-2 text-right">Companies</th>
            <th className="px-4 py-2 text-right">Score</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {segs.map((s, i) => (
            <tr key={i} className="hover-elevate">
              <td className="px-4 py-2 font-mono text-xs">{s.naics_code}</td>
              <td className="px-4 py-2 font-medium">{s.name}</td>
              <td className="px-4 py-2 text-muted-foreground">{s.sub_vertical}</td>
              <td className="px-4 py-2 text-right font-mono tabular-nums">
                {s.est_company_count?.toLocaleString?.() ?? "—"}
              </td>
              <td className="px-4 py-2 text-right font-mono tabular-nums text-primary">
                {s.opportunity_score}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function StakeholderGraph({ map }: { map?: StakeholderMap | null }) {
  const nodes = map?.nodes ?? [];
  const edges = map?.edges ?? [];
  if (nodes.length === 0)
    return <Empty label="Stakeholder graph not generated yet." />;
  return (
    <Card className="border-card-border bg-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="text-sm font-semibold">Buying committee</div>
        <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
          {nodes.length} stakeholders · {edges.length} relationships
        </div>
      </div>
      <StakeholderFlow nodes={nodes} edges={edges} />
      <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
        {nodes.map((n) => (
          <div
            key={n.id}
            className={`rounded border p-3 ${
              n.tier === "champion"
                ? "border-primary/40 bg-primary/5"
                : n.tier === "blocker"
                  ? "border-destructive/40 bg-destructive/5"
                  : "border-border bg-background/40"
            }`}
          >
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
              {n.tier}
            </div>
            <div className="mt-1 text-sm font-semibold">{n.label}</div>
            <div className="text-xs text-muted-foreground">{n.role}</div>
            <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary"
                style={{ width: `${n.influence ?? 0}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      {edges.length > 0 && (
        <div className="mt-5 border-t border-border pt-4">
          <div className="mb-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Influence
          </div>
          <ul className="space-y-1 font-mono text-xs">
            {edges.map((e, i) => (
              <li key={i} className="text-muted-foreground">
                <span className="text-foreground">{e.from}</span> →{" "}
                <span className="text-foreground">{e.to}</span>
                <span className="ml-2 text-primary">{e.label}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function UseCasesView({ use_cases }: { use_cases?: { use_cases?: UseCase[] } | null }) {
  const list = use_cases?.use_cases ?? [];
  if (list.length === 0)
    return <Empty label="Use case library not generated yet." />;
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {list.map((u, i) => (
        <Card key={i} className="border-card-border bg-card p-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <TrendingUp className="h-4 w-4 text-primary" />
            {u.title}
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-widest text-muted-foreground">
            {u.vertical} · {u.persona}
          </div>
          <div className="mt-2 text-xs text-muted-foreground">{u.scenario}</div>
          <div className="mt-2 text-sm font-medium text-primary">
            {u.value_prop}
          </div>
        </Card>
      ))}
    </div>
  );
}
