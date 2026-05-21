import { useRoute } from "wouter";
import { useState, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Brain,
  PlayCircle,
  Sparkles,
  TrendingUp,
  Building2,
  Map,
  Users,
  Target,
  BarChart3,
  Boxes,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import {
  useStrategy,
  useMarketSizing,
  useRunCompetitors,
  useCompetitors,
  usePatterns,
  useRunPatterns,
  useScoreLeads,
  useUpdateStrategy,
  useUpdateStrategySection,
  type Icp,
  type PersonaMatrix,
  type Persona,
  type ProblemRow,
  type NaicsSegment,
  type StakeholderMap,
  type UseCase,
  type StrategySection,
} from "@/hooks/useStrategies";
import { apiUrl } from "@/lib/api";
import { useFetchLimits } from "@/hooks/useSettings";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ReasoningPanel, SourceBadge } from "@/components/ReasoningPanel";
import { Empty } from "@/components/Empty";
import { StakeholderFlow } from "@/components/StakeholderFlow";
import { StatusPill } from "@/components/Pills";
import { EditableField } from "@/components/EditableField";
import { EditableTextarea } from "@/components/EditableTextarea";
import { EditableList } from "@/components/EditableList";
import { RetriggerBar, type RetriggerAction } from "@/components/RetriggerBar";

const S1_STAGES = [
  { key: "icp", label: "ICP" },
  { key: "personas", label: "Personas" },
  { key: "problems", label: "Problems" },
  { key: "naics", label: "NAICS" },
  { key: "stakeholders", label: "Stakeholders" },
  { key: "use-cases", label: "Use Cases" },
  { key: "market-sizing", label: "Market Sizing" },
];

export function StrategyDetail() {
  const [, params] = useRoute("/strategy/:id");
  const id = params?.id;
  const { data: strategy, isLoading } = useStrategy(id);
  const qc = useQueryClient();
  const [streaming, setStreaming] = useState(false);
  const [stageStatus, setStageStatus] = useState<Record<string, string>>({});
  const autoRanRef = useRef<string | null>(null);
  const sizing = useMarketSizing();
  const runComps = useRunCompetitors();
  const { data: competitors } = useCompetitors(id);
  const { data: patterns } = usePatterns(id);
  const runPatterns = useRunPatterns();
  const { data: fetchCaps } = useFetchLimits();
  const [marketLimit, setMarketLimit] = useState<string>("default");

  const updateStrategy = useUpdateStrategy();
  const updateSection = useUpdateStrategySection();
  const scoreLeads = useScoreLeads();
  const [dirty, setDirty] = useState(false);

  function onSaved() {
    setDirty(true);
  }

  async function saveField(data: {
    product_name?: string;
    description?: string;
    target_market?: string;
    pain_points_raw?: string;
  }) {
    if (!id) return;
    try {
      await updateStrategy.mutateAsync({ id, data });
      onSaved();
    } catch (err) {
      console.error("Failed to save field:", err);
    }
  }

  async function saveSection(section: StrategySection, data: object) {
    if (!id) return;
    try {
      await updateSection.mutateAsync({ id, section, data });
      onSaved();
    } catch (err) {
      console.error("Failed to save section:", err);
    }
  }

  const ready = strategy?.status === "ready";

  async function startStream() {
    if (!id) return;
    setStreaming(true);
    setStageStatus({});
    const es = new EventSource(apiUrl(`/api/strategies/${id}/run`));
    es.addEventListener("stage_start", (e) => {
      const d = JSON.parse((e as MessageEvent).data ?? "{}");
      setStageStatus((prev) => ({ ...prev, [d.stage]: "running" }));
    });
    es.addEventListener("stage_complete", (e) => {
      const d = JSON.parse((e as MessageEvent).data ?? "{}");
      setStageStatus((prev) => ({ ...prev, [d.stage]: "done" }));
      qc.invalidateQueries({ queryKey: ["strategy", id] });
    });
    es.addEventListener("complete", () => {
      setStreaming(false);
      es.close();
      qc.invalidateQueries({ queryKey: ["strategy", id] });
    });
    es.addEventListener("error", (e) => {
      console.error("SSE error", e);
      setStageStatus((prev) => {
        const update: Record<string, string> = {};
        for (const k of Object.keys(prev)) {
          if (prev[k] === "running") update[k] = "error";
        }
        return { ...prev, ...update };
      });
    });
    es.onerror = () => {
      setStreaming(false);
      es.close();
    };
  }

  useEffect(() => {
    if (
      strategy &&
      strategy.status === "draft" &&
      autoRanRef.current !== strategy.id
    ) {
      autoRanRef.current = strategy.id;
      startStream();
    }
  }, [strategy]);

  if (isLoading)
    return (
      <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading strategy…
      </div>
    );
  if (!strategy)
    return (
      <div className="rounded border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        Strategy not found.
      </div>
    );

  const retriggerActions: RetriggerAction[] = [
    {
      label: streaming ? "Running…" : "Re-run S1",
      icon: <PlayCircle className="h-3 w-3" />,
      onClick: startStream,
      isPending: streaming,
    },
    {
      label: "Re-score leads",
      icon: <Sparkles className="h-3 w-3" />,
      onClick: () => id && scoreLeads.mutate(id),
      isPending: scoreLeads.isPending,
    },
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 pb-16 pt-8">
      {/* Editable page header */}
      <div className="mb-6">
        <div className="text-[10px] font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Stage 1 · Strategy
        </div>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
          <EditableField
            value={strategy.product_name}
            onSave={(v) => saveField({ product_name: v })}
            displayClassName="text-2xl font-semibold"
            inputClassName="w-72 text-xl"
          />
        </h1>
        <div className="mt-1 max-w-2xl">
          <EditableTextarea
            value={strategy.description}
            onSave={(v) => saveField({ description: v })}
            textClassName="text-sm text-muted-foreground"
            rows={2}
            placeholder="Add a description…"
          />
        </div>
        {(strategy.target_market || strategy.pain_points_raw) && (
          <div className="mt-2 flex flex-wrap gap-5 text-sm">
            {strategy.target_market && (
              <div className="flex items-center gap-1.5">
                <span className="shrink-0 text-[10px] uppercase tracking-widest text-muted-foreground">
                  Target market:
                </span>
                <EditableField
                  value={strategy.target_market}
                  onSave={(v) => saveField({ target_market: v })}
                  displayClassName="text-sm text-foreground"
                />
              </div>
            )}
            {strategy.pain_points_raw && (
              <div className="flex items-center gap-1.5">
                <span className="shrink-0 text-[10px] uppercase tracking-widest text-muted-foreground">
                  Pain points:
                </span>
                <EditableField
                  value={strategy.pain_points_raw}
                  onSave={(v) => saveField({ pain_points_raw: v })}
                  displayClassName="text-sm text-foreground"
                />
              </div>
            )}
          </div>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <StatusPill status={strategy.status} />
          {!streaming && (
            <Button onClick={startStream} data-testid="button-run-s1">
              <PlayCircle className="mr-2 h-4 w-4" />
              {ready ? "Re-run S1" : "Run S1"}
            </Button>
          )}
          {streaming && <StreamProgress stageStatus={stageStatus} />}
        </div>
      </div>

      {/* Retrigger bar */}
      {dirty && !streaming && (
        <RetriggerBar
          actions={retriggerActions}
          onDismiss={() => setDirty(false)}
        />
      )}

      {/* Pipeline progress card */}
      <div className="mb-4">
        <Card className="border-card-border bg-card p-4">
          <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Pipeline
          </div>
          <div className="mt-2 flex flex-wrap gap-3">
            {S1_STAGES.map((stage) => {
              const status = stageStatus[stage.key];
              return (
                <div
                  key={stage.key}
                  className={`flex items-center gap-1.5 rounded px-2 py-1 text-xs ${
                    status === "done"
                      ? "bg-primary/10 text-primary"
                      : status === "running"
                        ? "bg-amber-500/10 text-amber-400"
                        : status === "error"
                          ? "bg-destructive/10 text-destructive"
                          : "bg-muted text-muted-foreground"
                  }`}
                >
                  {status === "running" ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : status === "done" ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : status === "error" ? (
                    <AlertCircle className="h-3 w-3" />
                  ) : null}
                  {stage.label}
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <Tabs defaultValue="icp" className="space-y-4">
        <TabsList className="flex h-auto flex-wrap gap-1">
          <TabsTrigger value="icp">
            <Target className="mr-1.5 h-3.5 w-3.5" />
            ICP
          </TabsTrigger>
          <TabsTrigger value="personas">
            <Users className="mr-1.5 h-3.5 w-3.5" />
            Personas
          </TabsTrigger>
          <TabsTrigger value="problems">
            <Brain className="mr-1.5 h-3.5 w-3.5" />
            Problems
          </TabsTrigger>
          <TabsTrigger value="naics">
            <Map className="mr-1.5 h-3.5 w-3.5" />
            NAICS
          </TabsTrigger>
          <TabsTrigger value="stakeholders">
            <Building2 className="mr-1.5 h-3.5 w-3.5" />
            Stakeholders
          </TabsTrigger>
          <TabsTrigger value="use-cases">
            <TrendingUp className="mr-1.5 h-3.5 w-3.5" />
            Use Cases
          </TabsTrigger>
          <TabsTrigger value="market-sizing">
            <BarChart3 className="mr-1.5 h-3.5 w-3.5" />
            Market Sizing
          </TabsTrigger>
          <TabsTrigger value="competitors">
            <Boxes className="mr-1.5 h-3.5 w-3.5" />
            Competitors
          </TabsTrigger>
          <TabsTrigger value="patterns">
            <Sparkles className="mr-1.5 h-3.5 w-3.5" />
            Patterns
          </TabsTrigger>
        </TabsList>

        <TabsContent value="icp" className="space-y-4">
          <ReasoningPanel
            provenance={strategy.icp?._provenance}
            fallback={{
              source: "ai_generated",
              logic:
                "ICP firmographics inferred from product description, target market, and stated pain points using the language model. Industries and geos are extracted then ranked by relevance.",
              steps: [
                "Parse product description for vertical signals",
                "Infer employee + revenue bands from pain point language",
                "Rank industries by semantic match to use cases",
              ],
            }}
          />
          <IcpView
            icp={strategy.icp}
            onSave={(d) => saveSection("icp", d)}
          />
        </TabsContent>

        <TabsContent value="personas" className="space-y-4">
          <ReasoningPanel
            provenance={strategy.personas?._provenance}
            fallback={{
              source: "ai_generated",
              logic:
                "Three-archetype persona matrix (champion, economic buyer, blocker) derived from ICP context and industry hiring patterns.",
              steps: [
                "Map ICP to common org chart roles",
                "Generate goals, frustrations, objections per archetype",
                "Add communication style guidance from seniority signals",
              ],
            }}
          />
          <PersonasView
            personas={strategy.personas}
            onSave={(d) => saveSection("personas", d)}
          />
        </TabsContent>

        <TabsContent value="problems" className="space-y-4">
          <ReasoningPanel
            provenance={strategy.problems?._provenance}
            fallback={{
              source: "ai_generated",
              logic:
                "Problem map cross-joins personas with pain categories, adds trigger events and urgency ratings, and proposes product angles.",
              steps: [
                "For each persona, enumerate top 3 pain themes",
                "Identify trigger events that raise urgency",
                "Map product capability to each pain",
              ],
            }}
          />
          <ProblemsView
            problems={strategy.problems}
            onSave={(d) => saveSection("problems", d)}
          />
        </TabsContent>

        <TabsContent value="naics" className="space-y-4">
          <ReasoningPanel
            fallback={{
              source: "ai_generated",
              logic:
                "NAICS codes selected by matching ICP industry keywords to the official NAICS taxonomy using semantic similarity, then ranked by estimated addressable company count.",
              steps: [
                "Embed ICP industries into vector space",
                "Retrieve top-N NAICS codes by cosine similarity",
                "Estimate company count from public census data",
              ],
            }}
          />
          <NaicsView naics={strategy.naics} />
        </TabsContent>

        <TabsContent value="stakeholders" className="space-y-4">
          <ReasoningPanel
            provenance={strategy.stakeholder_map?._provenance}
            fallback={{
              source: "ai_generated",
              logic:
                "Buying committee graph built from persona matrix plus typical enterprise org structures. Influence scores derived from role seniority and budget ownership.",
              steps: [
                "Enumerate stakeholders from persona definitions",
                "Assign influence weights by seniority tier",
                "Draw directed edges from reporting and approval paths",
              ],
            }}
          />
          <StakeholderGraph map={strategy.stakeholder_map} />
        </TabsContent>

        <TabsContent value="use-cases" className="space-y-4">
          <ReasoningPanel
            fallback={{
              source: "ai_generated",
              logic:
                "Use case library built from the cross-product of ICP verticals and persona roles, anchored to the product's core value proposition.",
              steps: [
                "Enumerate vertical × persona combinations",
                "For each pair, generate a scenario + value prop",
                "Rank by ICP segment fit score",
              ],
            }}
          />
          <UseCasesView
            use_cases={strategy.use_cases}
            onSave={(d) => saveSection("use-cases", d)}
          />
        </TabsContent>

        <TabsContent value="market-sizing" className="space-y-4">
          <ReasoningPanel
            provenance={strategy.tam_sam_som?._provenance}
            fallback={{
              source: "ai_generated",
              logic:
                "TAM/SAM/SOM modelled top-down from ICP employee size range × estimated NAICS company count × average contract value proxy.",
              steps: [
                "Estimate total addressable company count from NAICS + ICP",
                "Apply ICP fit rate for SAM",
                "Apply win-rate / reachable % for SOM",
              ],
            }}
          />
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <Select value={marketLimit} onValueChange={setMarketLimit}>
              <SelectTrigger className="h-8 w-36 text-xs">
                <SelectValue
                  placeholder={`Limit: ${fetchCaps?.limits.market_sizing_results ?? "default"}`}
                />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">
                  Default ({fetchCaps?.limits.market_sizing_results ?? 1})
                </SelectItem>
                {[1, 3, 5].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} source{n > 1 ? "s" : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              variant="secondary"
              disabled={sizing.isPending}
              onClick={() =>
                id &&
                sizing.mutate({
                  id,
                  limit:
                    marketLimit && marketLimit !== "default"
                      ? Number(marketLimit)
                      : undefined,
                })
              }
              data-testid="button-run-market-sizing"
            >
              {sizing.isPending ? "Sizing…" : "Run market sizing"}
            </Button>
          </div>
          {strategy.tam_sam_som ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                {(["tam", "sam", "som"] as const).map((k) => {
                  const block = strategy.tam_sam_som?.[k];
                  return (
                    <Card key={k} className="border-card-border bg-card p-5">
                      <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                        {k.toUpperCase()}
                      </div>
                      <div className="mt-2 font-mono text-3xl tabular-nums text-foreground">
                        {block?.value_usd != null
                          ? fmtMoney(block.value_usd)
                          : "—"}
                      </div>
                      {block?.label && (
                        <div className="mt-1 text-xs text-muted-foreground">
                          {block.label}
                        </div>
                      )}
                    </Card>
                  );
                })}
              </div>
              {strategy.tam_sam_som.methodology && (
                <Card className="border-card-border bg-card p-4">
                  <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                    Methodology
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    {strategy.tam_sam_som.methodology}
                  </div>
                </Card>
              )}
            </div>
          ) : (
            <Empty label="Market sizing not generated yet." />
          )}
        </TabsContent>

        <TabsContent value="competitors" className="space-y-4">
          <ReasoningPanel
            fallback={{
              source: "serpapi",
              logic:
                "Competitor profiles built from SerpAPI organic search queries for the product category + 'alternatives' / 'pricing', then enriched by the model.",
              steps: [
                "Search '[product] alternatives' via SerpAPI",
                "Extract competitor names and landing page copy",
                "Model-generate positioning, features, weaknesses",
              ],
            }}
          />
          <div className="mb-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={runComps.isPending}
              onClick={() => id && runComps.mutate(id)}
              data-testid="button-run-competitors"
            >
              {runComps.isPending ? "Running…" : "Run competitor analysis"}
            </Button>
          </div>
          {competitors && competitors.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {competitors.map((c) => (
                <Card key={c.id} className="border-card-border bg-card p-4">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-semibold">{c.name}</div>
                    {c.g2_rating != null && (
                      <div className="font-mono text-xs text-primary">
                        G2 {c.g2_rating?.toFixed(1)}
                      </div>
                    )}
                  </div>
                  {c.website && (
                    <div className="text-[11px] text-muted-foreground">
                      {c.website}
                    </div>
                  )}
                  {c.positioning && (
                    <div className="mt-2 text-xs text-muted-foreground">
                      {c.positioning}
                    </div>
                  )}
                  {(c.weaknesses ?? []).length > 0 && (
                    <div className="mt-2">
                      <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                        Weaknesses
                      </div>
                      <ul className="mt-1 space-y-0.5 text-xs text-foreground/70">
                        {c.weaknesses!.map((w, i) => (
                          <li key={i} className="flex gap-1">
                            <span className="text-destructive">×</span> {w}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          ) : (
            <Empty label="Competitor analysis not run yet." />
          )}
        </TabsContent>

        <TabsContent value="patterns" className="space-y-4">
          <ReasoningPanel
            fallback={{
              source: "computed",
              logic:
                "Pattern clusters derived from k-means on contact signal vectors. Conversion rate estimated from qualification status.",
              steps: [
                "Embed each contact's signal combination",
                "K-means cluster with k=5",
                "Compute cluster conversion rate from qualified contacts",
              ],
            }}
          />
          <div className="mb-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={runPatterns.isPending}
              onClick={() => id && runPatterns.mutate(id)}
              data-testid="button-run-patterns"
            >
              {runPatterns.isPending ? "Clustering…" : "Run pattern recognition"}
            </Button>
          </div>
          {patterns && patterns.length > 0 ? (
            <Card className="border-card-border bg-card p-0 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/40">
                  <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                    <th className="px-4 py-2">Pattern</th>
                    <th className="px-4 py-2">Signals</th>
                    <th className="px-4 py-2 text-right">Conv. rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {patterns.map((p) => (
                    <tr key={p.id} className="hover-elevate">
                      <td className="px-4 py-2 font-medium">{p.pattern_name}</td>
                      <td className="px-4 py-2">
                        <div className="flex flex-wrap gap-1">
                          {(p.signal_combination ?? []).map((s, i) => (
                            <span
                              key={i}
                              className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
                            >
                              {s}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums text-primary">
                        {(p.conversion_rate * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          ) : (
            <Empty label="No patterns detected yet." />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StreamProgress({
  stageStatus,
}: {
  stageStatus: Record<string, string>;
}) {
  const running = Object.values(stageStatus).filter((v) => v === "running");
  const done = Object.values(stageStatus).filter((v) => v === "done");
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin text-primary" />
      <span>
        {running.length > 0
          ? `Running ${running.length} stage${running.length > 1 ? "s" : ""}…`
          : `Completed ${done.length} stage${done.length > 1 ? "s" : ""}`}
      </span>
    </div>
  );
}

function fmtMoney(v: number | undefined): string {
  if (v == null) return "—";
  if (v >= 1_000_000_000) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1_000_000) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v}`;
}

function fmtRange(v: unknown, money = false): string | undefined {
  if (v == null) return undefined;
  if (typeof v === "string" || typeof v === "number") return String(v);
  if (typeof v === "object") {
    const o = v as { min?: number | string; max?: number | string };
    const fmt = (n: number | string | undefined) => {
      if (n == null || n === "") return "?";
      if (!money) return String(n);
      const num = typeof n === "number" ? n : Number(n);
      if (!isFinite(num)) return String(n);
      if (num >= 1_000_000_000) return `$${(num / 1e9).toFixed(1)}B`;
      if (num >= 1_000_000) return `$${(num / 1e6).toFixed(1)}M`;
      if (num >= 1_000) return `$${(num / 1e3).toFixed(0)}K`;
      return `$${num}`;
    };
    return `${fmt(o.min)}–${fmt(o.max)}`;
  }
  return undefined;
}

function IcpView({
  icp,
  onSave,
}: {
  icp?: Icp | null;
  onSave: (patch: object) => Promise<void>;
}) {
  if (!icp) return <Empty label="ICP not generated yet." />;
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Card className="border-card-border bg-card p-5">
        <div className="mb-3 text-sm font-semibold">Firmographics</div>
        <dl className="space-y-3 text-sm">
          <div className="space-y-1">
            <dt className="text-xs uppercase tracking-widest text-muted-foreground">
              Industries
            </dt>
            <dd>
              <EditableList
                items={icp.industries ?? []}
                onSave={(v) => onSave({ industries: v })}
                placeholder="Click to add industries"
              />
            </dd>
          </div>
          <div className="flex items-start justify-between gap-4">
            <dt className="shrink-0 text-xs uppercase tracking-widest text-muted-foreground">
              Employee size
            </dt>
            <dd className="text-right">
              <EditableField
                value={fmtRange(icp.employee_size_range) ?? ""}
                onSave={(v) => onSave({ employee_size_range: v })}
                placeholder="e.g. 50–500"
                displayClassName="text-sm text-foreground"
              />
            </dd>
          </div>
          <div className="flex items-start justify-between gap-4">
            <dt className="shrink-0 text-xs uppercase tracking-widest text-muted-foreground">
              Revenue
            </dt>
            <dd className="text-right">
              <EditableField
                value={fmtRange(icp.revenue_range, true) ?? ""}
                onSave={(v) => onSave({ revenue_range: v })}
                placeholder="e.g. $1M–$50M"
                displayClassName="text-sm text-foreground"
              />
            </dd>
          </div>
          <div className="space-y-1">
            <dt className="text-xs uppercase tracking-widest text-muted-foreground">
              Geographies
            </dt>
            <dd>
              <EditableList
                items={icp.geographies ?? []}
                onSave={(v) => onSave({ geographies: v })}
                placeholder="Click to add geographies"
              />
            </dd>
          </div>
          <div className="space-y-1">
            <dt className="text-xs uppercase tracking-widest text-muted-foreground">
              Tech signals
            </dt>
            <dd>
              <EditableList
                items={icp.tech_stack_signals ?? []}
                onSave={(v) => onSave({ tech_stack_signals: v })}
                placeholder="Click to add tech stack signals"
              />
            </dd>
          </div>
        </dl>
      </Card>

      <Card className="border-card-border bg-card p-5">
        <div className="mb-3 text-sm font-semibold">Segments</div>
        <div className="space-y-3">
          {(icp.segments ?? []).map((seg, i) => (
            <div
              key={i}
              className="rounded border border-border bg-background/40 p-3"
            >
              <div className="flex items-start justify-between gap-2">
                <EditableField
                  value={seg.name}
                  onSave={(v) => {
                    const newSegs = [...(icp.segments ?? [])];
                    newSegs[i] = { ...newSegs[i], name: v };
                    return onSave({ segments: newSegs });
                  }}
                  displayClassName="text-sm font-medium"
                />
                <span className="shrink-0 font-mono text-xs text-primary">
                  {seg.fit_score?.toFixed(0) ?? "?"}
                </span>
              </div>
              {seg.rationale && (
                <EditableField
                  value={seg.rationale}
                  onSave={(v) => {
                    const newSegs = [...(icp.segments ?? [])];
                    newSegs[i] = { ...newSegs[i], rationale: v };
                    return onSave({ segments: newSegs });
                  }}
                  className="mt-1"
                  displayClassName="text-xs text-muted-foreground"
                />
              )}
            </div>
          ))}
          {(icp.segments ?? []).length === 0 && (
            <div className="text-xs text-muted-foreground">
              No segments defined.
            </div>
          )}
        </div>
        {(icp.scoring_rules ?? []).length > 0 && (
          <div className="mt-4 border-t border-border pt-4">
            <div className="mb-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
              Scoring rules
            </div>
            <div className="space-y-1">
              {icp.scoring_rules!.map((r, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-foreground/80">{r.signal}</span>
                  <span className="font-mono text-primary">+{r.weight}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

function PersonasView({
  personas,
  onSave,
}: {
  personas?: PersonaMatrix | null;
  onSave: (patch: object) => Promise<void>;
}) {
  if (!personas) return <Empty label="Personas not generated yet." />;

  const types: { key: string; label: string }[] = [
    { key: "champion", label: "Champion" },
    { key: "economic_buyer", label: "Economic buyer" },
    { key: "blocker", label: "Blocker" },
  ];

  function updatePersona(key: string, update: Partial<Persona>) {
    // Handle both { "champion": {...} } and { "personas": { "champion": {...} } } shapes
    const root = (personas as any).personas ? (personas as any).personas : personas;
    const current = (root as Record<string, Persona | undefined>)[key] ?? {};
    
    // If the data was wrapped, preserve the wrapper on save
    if ((personas as any).personas) {
      return onSave({ personas: { ...root, [key]: { ...current, ...update } } });
    }
    return onSave({ [key]: { ...current, ...update } });
  }

  // Handle both { "champion": {...} } and { "personas": { "champion": {...} } } shapes
  const rootPersonas = (personas as any).personas ? (personas as any).personas : personas;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {types.map(({ key, label }) => {
        const p = (rootPersonas as Record<string, Persona | undefined>)[key];
        if (!p) return null;
        return (
          <Card key={key} className="border-card-border bg-card p-5">
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
              {label}
            </div>
            <div className="mt-1">
              <EditableField
                value={p.title ?? ""}
                onSave={(v) => updatePersona(key, { title: v })}
                displayClassName="text-base font-semibold"
                placeholder="Title"
              />
            </div>
            <EditableSection
              label="Goals"
              items={p.goals ?? []}
              onSave={(items) => updatePersona(key, { goals: items })}
            />
            <EditableSection
              label="Frustrations"
              items={p.frustrations ?? []}
              onSave={(items) => updatePersona(key, { frustrations: items })}
            />
            <EditableSection
              label="Objections"
              items={p.objections ?? []}
              onSave={(items) => updatePersona(key, { objections: items })}
            />
            {p.communication_style !== undefined && (
              <div className="mt-3">
                <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  Communication
                </div>
                <div className="mt-1">
                  <EditableField
                    value={p.communication_style ?? ""}
                    onSave={(v) =>
                      updatePersona(key, { communication_style: v })
                    }
                    displayClassName="text-xs italic text-muted-foreground"
                    placeholder="Communication style"
                  />
                </div>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

function EditableSection({
  label,
  items,
  onSave,
}: {
  label: string;
  items: string[];
  onSave: (items: string[]) => Promise<void> | void;
}) {
  return (
    <div className="mt-3">
      <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className="mt-1">
        <EditableList
          items={items}
          onSave={onSave}
          placeholder={`Click to add ${label.toLowerCase()}`}
        />
      </div>
    </div>
  );
}

const URGENCY_OPTIONS = ["low", "medium", "high"] as const;

function ProblemsView({
  problems,
  onSave,
}: {
  problems?: { problems?: ProblemRow[] } | null;
  onSave: (patch: object) => Promise<void>;
}) {
  const list = problems?.problems ?? [];
  if (list.length === 0) return <Empty label="Problem map not generated yet." />;

  function updateRow(i: number, update: Partial<ProblemRow>) {
    const newList = list.map((p, idx) => (idx === i ? { ...p, ...update } : p));
    return onSave({ problems: newList });
  }

  return (
    <Card className="border-card-border bg-card p-0">
      <div className="divide-y divide-border">
        {list.map((p, i) => (
          <div key={i} className="grid grid-cols-12 gap-4 p-4">
            <div className="col-span-2">
              <EditableField
                value={p.persona}
                onSave={(v) => updateRow(i, { persona: v })}
                displayClassName="text-xs uppercase tracking-widest text-muted-foreground"
              />
            </div>
            <div className="col-span-7">
              <EditableField
                value={p.pain}
                onSave={(v) => updateRow(i, { pain: v })}
                displayClassName="text-sm font-medium"
              />
              <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                <span className="shrink-0 opacity-60">Trigger:</span>
                <EditableField
                  value={p.trigger}
                  onSave={(v) => updateRow(i, { trigger: v })}
                  displayClassName="text-xs text-muted-foreground"
                />
              </div>
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <span className="shrink-0 opacity-60">Angle:</span>
                <EditableField
                  value={p.product_angle}
                  onSave={(v) => updateRow(i, { product_angle: v })}
                  displayClassName="text-xs text-muted-foreground"
                />
              </div>
            </div>
            <div className="col-span-3">
              <Select
                value={p.urgency}
                onValueChange={(v) =>
                  updateRow(i, { urgency: v as ProblemRow["urgency"] })
                }
              >
                <SelectTrigger className="h-7 text-[10px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {URGENCY_OPTIONS.map((u) => (
                    <SelectItem key={u} value={u}>
                      {u} urgency
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function NaicsView({
  naics,
}: {
  naics?: { segments?: NaicsSegment[] } | null;
}) {
  const segs = naics?.segments ?? [];
  if (segs.length === 0)
    return <Empty label="NAICS segmentation not generated yet." />;
  return (
    <Card className="border-card-border bg-card overflow-hidden p-0">
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
              <td className="px-4 py-2 text-muted-foreground">
                {s.sub_vertical}
              </td>
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
                {e.label && (
                  <span className="ml-2 text-primary">{e.label}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function UseCasesView({
  use_cases,
  onSave,
}: {
  use_cases?: { use_cases?: UseCase[] } | null;
  onSave: (patch: object) => Promise<void>;
}) {
  const list = use_cases?.use_cases ?? [];
  if (list.length === 0)
    return <Empty label="Use case library not generated yet." />;

  function updateCard(i: number, update: Partial<UseCase>) {
    const newList = list.map((u, idx) =>
      idx === i ? { ...u, ...update } : u,
    );
    return onSave({ use_cases: newList });
  }

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {list.map((u, i) => (
        <Card key={i} className="border-card-border bg-card p-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 shrink-0 text-primary" />
            <EditableField
              value={u.title}
              onSave={(v) => updateCard(i, { title: v })}
              displayClassName="text-sm font-semibold"
            />
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-widest text-muted-foreground">
            {u.vertical} · {u.persona}
          </div>
          {u.scenario !== undefined && (
            <EditableTextarea
              value={u.scenario ?? ""}
              onSave={(v) => updateCard(i, { scenario: v })}
              className="mt-2"
              textClassName="text-xs text-muted-foreground"
              rows={3}
              placeholder="Describe the scenario…"
            />
          )}
          {u.value_prop !== undefined && (
            <EditableField
              value={u.value_prop ?? ""}
              onSave={(v) => updateCard(i, { value_prop: v })}
              className="mt-2"
              displayClassName="text-sm font-medium text-primary"
              placeholder="Value proposition…"
            />
          )}
        </Card>
      ))}
    </div>
  );
}
