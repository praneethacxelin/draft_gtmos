import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/PageHeader";
import { SentimentChip } from "@/components/Pills";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { useContacts } from "@/hooks/useContacts";
import { useAccounts } from "@/hooks/useAccounts";
import {
  useEngagementEvents,
  useCreateEvent,
  useIntentScores,
  useScoreIntent,
  useFeedback,
  useCreateFeedback,
  useAttribution,
  useCreateAttribution,
  useQualificationSummary,
  useQualifyContact,
  useLoopBack,
  useRunLoopBack,
  useApplyLoopBack,
} from "@/hooks/useM3";
import { fmtRelative } from "@/lib/format";
import { Activity, RefreshCcw, MessagesSquare, Workflow, Check } from "lucide-react";
import { ReasoningPanel, SourceBadge } from "@/components/ReasoningPanel";
import { RetriggerBar, type RetriggerAction } from "@/components/RetriggerBar";

export function Intelligence() {
  const { activeId, active } = useActiveStrategy();

  if (!activeId) {
    return (
      <div className="rounded border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        Select an active strategy to view intelligence.
      </div>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="M3 · Intelligence loop"
        title="Intelligence"
        subtitle={`Engagement, intent, feedback, attribution, qualification, and ICP loop-back for ${active?.product_name ?? ""}.`}
      />
      <Tabs defaultValue="engagement" className="space-y-4">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="engagement">Engagement</TabsTrigger>
          <TabsTrigger value="intent">Intent</TabsTrigger>
          <TabsTrigger value="feedback">Feedback</TabsTrigger>
          <TabsTrigger value="attribution">Attribution</TabsTrigger>
          <TabsTrigger value="qualification">Qualification</TabsTrigger>
          <TabsTrigger value="loop-back">Loop-back</TabsTrigger>
        </TabsList>

        <TabsContent value="engagement" className="space-y-4">
          <ReasoningPanel
            fallback={{
              source: "computed",
              logic: "Engagement events are stored verbatim and weighted by event_type to produce per-account intent.",
            }}
          />
          <EngagementTab strategyId={activeId} />
        </TabsContent>
        <TabsContent value="intent" className="space-y-4">
          <ReasoningPanel
            fallback={{
              source: "computed",
              logic: "Account intent = sum of weighted engagement events bucketed into low / medium / high.",
              steps: [
                "Sum event weights per account",
                "Bucket score into classification thresholds",
                "Persist score on Account row",
              ],
            }}
          />
          <IntentTab strategyId={activeId} />
        </TabsContent>
        <TabsContent value="feedback" className="space-y-4">
          <ReasoningPanel
            fallback={{
              source: "ai_generated",
              logic: "Sentiment + themes auto-extracted by the model from each verbatim feedback entry.",
            }}
          />
          <FeedbackTab strategyId={activeId} />
        </TabsContent>
        <TabsContent value="attribution" className="space-y-4">
          <ReasoningPanel
            fallback={{
              source: "computed",
              logic: "Channel attribution rolled up deterministically from logged AttributionEvent rows.",
            }}
          />
          <AttributionTab strategyId={activeId} />
        </TabsContent>
        <TabsContent value="qualification" className="space-y-4">
          <ReasoningPanel
            fallback={{
              source: "computed",
              logic: "MQL/SQL/Nurture buckets derived from each contact's composite total score.",
            }}
          />
          <QualificationTab strategyId={activeId} />
        </TabsContent>
        <TabsContent value="loop-back" className="space-y-4">
          <ReasoningPanel
            fallback={{
              source: "ai_generated",
              logic: "Aggregates qualification, attribution, and feedback themes, then asks the model to suggest concrete ICP refinements.",
            }}
          />
          <LoopBackTab strategyId={activeId} />
        </TabsContent>
      </Tabs>
    </>
  );
}

function EngagementTab({ strategyId }: { strategyId: string }) {
  const { data: events } = useEngagementEvents(strategyId);
  const { data: accounts } = useAccounts(strategyId);
  const create = useCreateEvent();
  const score = useScoreIntent();
  const [form, setForm] = useState({
    account_id: "",
    channel: "website",
    event_type: "page_view",
  });
  const [dirty, setDirty] = useState(false);

  const retriggerActions: RetriggerAction[] = [
    {
      label: score.isPending ? "Scoring…" : "Recompute intent",
      icon: <RefreshCcw className="h-3 w-3" />,
      onClick: () => score.mutate(strategyId),
      isPending: score.isPending,
    },
  ];

  return (
    <div className="space-y-4">
    {dirty && (
      <RetriggerBar
        message="Event captured."
        actions={retriggerActions}
        onDismiss={() => setDirty(false)}
      />
    )}
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2 border-card-border bg-card p-5">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <Activity className="h-4 w-4 text-primary" />
          Recent engagement
        </div>
        <div className="space-y-1">
          {events?.map((e) => (
            <div
              key={e.id}
              className="flex items-center justify-between rounded border border-border bg-background/40 px-3 py-2 text-xs"
            >
              <div className="flex items-center gap-3">
                <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  {e.channel}
                </span>
                <span className="font-medium text-foreground">
                  {e.event_type}
                </span>
              </div>
              <div className="flex items-center gap-3 text-muted-foreground">
                <span className="font-mono tabular-nums text-primary">
                  +{e.intent_contribution_score?.toFixed(0) ?? 1}
                </span>
                <span>{fmtRelative(e.occurred_at)}</span>
              </div>
            </div>
          ))}
          {(!events || events.length === 0) && (
            <div className="rounded border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
              No engagement captured yet.
            </div>
          )}
        </div>
      </Card>

      <Card className="border-card-border bg-card p-5">
        <div className="mb-3 text-sm font-semibold">Inject demo event</div>
        <div className="space-y-3">
          <div>
            <Label className="text-xs">Account</Label>
            <Select
              value={form.account_id}
              onValueChange={(v) => setForm({ ...form, account_id: v })}
            >
              <SelectTrigger className="h-9 text-xs">
                <SelectValue placeholder="Select account" />
              </SelectTrigger>
              <SelectContent>
                {accounts?.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.company_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Channel</Label>
            <Select
              value={form.channel}
              onValueChange={(v) => setForm({ ...form, channel: v })}
            >
              <SelectTrigger className="h-9 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["website", "email", "ads", "linkedin"].map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Event type</Label>
            <Select
              value={form.event_type}
              onValueChange={(v) => setForm({ ...form, event_type: v })}
            >
              <SelectTrigger className="h-9 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[
                  "page_view",
                  "pricing_view",
                  "case_study_view",
                  "demo_request",
                  "ad_click",
                  "video_view",
                  "form_fill",
                  "email_open",
                ].map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            disabled={!form.account_id || create.isPending}
            onClick={() => {
              create.mutate(
                {
                  strategy_id: strategyId,
                  account_id: form.account_id,
                  channel: form.channel,
                  event_type: form.event_type,
                },
                { onSuccess: () => setDirty(true) },
              );
            }}
            data-testid="button-create-event"
          >
            {create.isPending ? "Saving…" : "Capture event"}
          </Button>
        </div>
      </Card>
    </div>
    </div>
  );
}

function IntentTab({ strategyId }: { strategyId: string }) {
  const { data: rows } = useIntentScores(strategyId);
  const score = useScoreIntent();
  return (
    <Card className="border-card-border bg-card p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm font-semibold">Account-level intent</div>
        <Button
          size="sm"
          variant="secondary"
          disabled={score.isPending}
          onClick={() => score.mutate(strategyId)}
          data-testid="button-score-intent"
        >
          <RefreshCcw className="mr-2 h-4 w-4" />
          {score.isPending ? "Scoring…" : "Recompute"}
        </Button>
      </div>
      <div className="space-y-2">
        {rows?.map((r) => (
          <div
            key={r.account_id}
            className="rounded border border-border bg-background/40 p-3"
          >
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium">{r.company_name}</div>
              <div className="flex items-center gap-3">
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-widest ${
                    r.classification === "high"
                      ? "bg-primary/15 text-primary"
                      : r.classification === "medium"
                        ? "bg-amber-500/15 text-amber-400"
                        : "bg-muted text-muted-foreground"
                  }`}
                >
                  {r.classification}
                </span>
                <span className="font-mono text-sm tabular-nums">
                  {r.score.toFixed(0)}
                </span>
                <SourceBadge source="ai_generated" />
              </div>
            </div>
            <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary"
                style={{ width: `${Math.min(100, r.score)}%` }}
              />
            </div>
          </div>
        ))}
        {(!rows || rows.length === 0) && (
          <div className="rounded border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
            No intent scored yet — click Recompute.
          </div>
        )}
      </div>
    </Card>
  );
}

function FeedbackTab({ strategyId }: { strategyId: string }) {
  const { data: list } = useFeedback(strategyId);
  const create = useCreateFeedback();
  const run = useRunLoopBack();
  const [text, setText] = useState("");
  const [source, setSource] = useState("survey");
  const [dirty, setDirty] = useState(false);

  const retriggerActions: RetriggerAction[] = [
    {
      label: run.isPending ? "Analyzing…" : "Run loop-back",
      icon: <Workflow className="h-3 w-3" />,
      onClick: () => run.mutate(strategyId),
      isPending: run.isPending,
    },
  ];

  return (
    <div className="space-y-4">
    {dirty && (
      <RetriggerBar
        message="Feedback captured."
        actions={retriggerActions}
        onDismiss={() => setDirty(false)}
      />
    )}
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="border-card-border bg-card p-5">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <MessagesSquare className="h-4 w-4 text-primary" />
          Capture feedback
        </div>
        <div className="space-y-3">
          <div>
            <Label className="text-xs">Source</Label>
            <Select value={source} onValueChange={setSource}>
              <SelectTrigger className="h-9 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["survey", "nps", "form", "rating", "review"].map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Verbatim</Label>
            <Textarea
              rows={4}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="What did the customer say?"
            />
          </div>
          <Button
            disabled={!text || create.isPending}
            onClick={async () => {
              await create.mutateAsync({
                strategy_id: strategyId,
                source,
                raw_text: text,
              });
              setText("");
              setDirty(true);
            }}
            data-testid="button-capture-feedback"
          >
            {create.isPending ? "Analyzing…" : "Capture & extract"}
          </Button>
        </div>
      </Card>

      <Card className="lg:col-span-2 border-card-border bg-card p-5">
        <div className="mb-3 text-sm font-semibold">Recent feedback</div>
        <div className="space-y-2">
          {list?.map((f) => (
            <div
              key={f.id}
              className="rounded border border-border bg-background/40 p-3"
            >
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    {f.source}
                  </span>
                  <SentimentChip sentiment={f.sentiment} />
                </div>
                <div className="font-mono text-muted-foreground">
                  {fmtRelative(f.captured_at)}
                </div>
              </div>
              <div className="mt-2 text-sm italic text-foreground/90">
                "{f.raw_text}"
              </div>
              {(f.themes ?? []).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {f.themes!.map((t, i) => (
                    <span
                      key={i}
                      className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-primary"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
          {(!list || list.length === 0) && (
            <div className="rounded border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
              No feedback captured.
            </div>
          )}
        </div>
      </Card>
    </div>
    </div>
  );
}

function AttributionTab({ strategyId }: { strategyId: string }) {
  const { data: rows } = useAttribution(strategyId);
  const create = useCreateAttribution();
  const [form, setForm] = useState({
    source_channel: "email",
    conversion_event: "demo_booked",
    conversion_value: 0,
  });

  const max = Math.max(1, ...(rows?.map((r) => r.count) ?? [1]));

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2 border-card-border bg-card p-5">
        <div className="mb-3 text-sm font-semibold">Channel attribution</div>
        <div className="space-y-2">
          {rows?.map((r) => (
            <div key={r.channel}>
              <div className="flex justify-between text-xs">
                <span className="font-medium">{r.channel}</span>
                <span className="font-mono text-muted-foreground">
                  {r.count} touches · ${r.value.toLocaleString()}
                </span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary"
                  style={{ width: `${(r.count / max) * 100}%` }}
                />
              </div>
            </div>
          ))}
          {(!rows || rows.length === 0) && (
            <div className="rounded border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
              No conversions captured yet.
            </div>
          )}
        </div>
      </Card>

      <Card className="border-card-border bg-card p-5">
        <div className="mb-3 text-sm font-semibold">Log conversion</div>
        <div className="space-y-3">
          <div>
            <Label className="text-xs">Source channel</Label>
            <Input
              value={form.source_channel}
              onChange={(e) =>
                setForm({ ...form, source_channel: e.target.value })
              }
            />
          </div>
          <div>
            <Label className="text-xs">Conversion event</Label>
            <Select
              value={form.conversion_event}
              onValueChange={(v) => setForm({ ...form, conversion_event: v })}
            >
              <SelectTrigger className="h-9 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["demo_booked", "trial_started", "deal_created", "renewal"].map(
                  (c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Value (USD)</Label>
            <Input
              type="number"
              value={form.conversion_value}
              onChange={(e) =>
                setForm({ ...form, conversion_value: Number(e.target.value) })
              }
            />
          </div>
          <Button
            disabled={create.isPending}
            onClick={() =>
              create.mutate({ strategy_id: strategyId, ...form })
            }
            data-testid="button-log-attribution"
          >
            {create.isPending ? "Saving…" : "Log conversion"}
          </Button>
        </div>
      </Card>
    </div>
  );
}

function QualificationTab({ strategyId }: { strategyId: string }) {
  const { data: summary } = useQualificationSummary(strategyId);
  const { data: contacts } = useContacts(strategyId);
  const qualify = useQualifyContact();

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {(["sql", "mql", "nurture"] as const).map((k) => (
          <Card key={k} className="border-card-border bg-card p-5">
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
              {k}
            </div>
            <div className="mt-2 font-mono text-3xl tabular-nums">
              {summary?.[k] ?? 0}
            </div>
          </Card>
        ))}
      </div>
      <Card className="border-card-border bg-card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
              <th className="px-4 py-2">Contact</th>
              <th className="px-4 py-2">Company</th>
              <th className="px-4 py-2">Total score</th>
              <th className="px-4 py-2 text-right">Qualify</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {contacts?.slice(0, 25).map((c) => (
              <tr key={c.id} className="hover-elevate">
                <td className="px-4 py-2">
                  <div className="font-medium">{c.full_name}</div>
                  <div className="text-[11px] text-muted-foreground">
                    {c.title}
                  </div>
                </td>
                <td className="px-4 py-2 text-muted-foreground">
                  {c.company_name}
                </td>
                <td className="px-4 py-2 font-mono tabular-nums">
                  <span className="inline-flex items-center gap-2">
                    {c.total_score.toFixed(0)}
                    <SourceBadge source="ai_generated" />
                  </span>
                </td>
                <td className="px-4 py-2 text-right">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={qualify.isPending}
                    onClick={() => qualify.mutate(c.id)}
                    data-testid={`button-qualify-${c.id}`}
                  >
                    Qualify
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function LoopBackTab({ strategyId }: { strategyId: string }) {
  const { data: list } = useLoopBack(strategyId);
  const run = useRunLoopBack();
  const apply = useApplyLoopBack();

  return (
    <Card className="border-card-border bg-card p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Workflow className="h-4 w-4 text-primary" />
          ICP loop-back history
        </div>
        <Button
          size="sm"
          variant="secondary"
          disabled={run.isPending}
          onClick={() => run.mutate(strategyId)}
          data-testid="button-run-loop-back"
        >
          {run.isPending ? "Analyzing…" : "Run loop-back"}
        </Button>
      </div>
      <div className="space-y-3">
        {list?.map((u) => (
          <div
            key={u.id}
            className="rounded border border-border bg-background/40 p-4"
          >
            <div className="flex items-center justify-between text-xs">
              <div className="font-mono text-muted-foreground">
                {fmtRelative(u.created_at)}
              </div>
              {u.applied ? (
                <span className="inline-flex items-center gap-1 rounded bg-primary/15 px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-primary">
                  <Check className="h-3 w-3" /> Applied
                </span>
              ) : (
                <Button
                  size="sm"
                  onClick={() => apply.mutate(u.id)}
                  data-testid={`button-apply-${u.id}`}
                >
                  Apply
                </Button>
              )}
            </div>
            {u.delta?.rationale && (
              <div className="mt-2 text-sm italic text-foreground/90">
                {u.delta.rationale}
              </div>
            )}
            {(u.delta?.changes ?? []).length > 0 && (
              <div className="mt-3 space-y-1">
                {u.delta!.changes!.map((c, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-12 gap-2 rounded border border-border bg-background/60 p-2 text-xs"
                  >
                    <div className="col-span-3 font-mono text-muted-foreground">
                      {c.field}
                    </div>
                    <div className="col-span-3 line-through text-muted-foreground">
                      {String(c.current_value ?? "—")}
                    </div>
                    <div className="col-span-3 font-medium text-primary">
                      {String(c.suggested_value ?? "—")}
                    </div>
                    <div className="col-span-3 text-muted-foreground">
                      {c.reason}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {(!list || list.length === 0) && (
          <div className="rounded border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
            No loop-back updates yet.
          </div>
        )}
      </div>
    </Card>
  );
}
