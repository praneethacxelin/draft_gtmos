import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/PageHeader";
import { TierBadge, ScoreBar, DemoBadge } from "@/components/Pills";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { usePrioritizedAccounts } from "@/hooks/useAccounts";
import { useContacts } from "@/hooks/useContacts";
import { useSignals } from "@/hooks/useSignals";
import {
  useLeadSearch,
  useRunSignals,
  useScoreLeads,
  useRunPatterns,
} from "@/hooks/useStrategies";
import { fmtRelative } from "@/lib/format";
import { Search, Radar, Sparkles, Crosshair, Building2 } from "lucide-react";

export function Prospects() {
  const { active, activeId } = useActiveStrategy();
  const [tierFilter, setTierFilter] = useState<string>("all");
  const tier = tierFilter === "all" ? undefined : Number(tierFilter);

  const { data: prioritized } = usePrioritizedAccounts(activeId ?? undefined);
  const { data: contacts } = useContacts(activeId ?? undefined, tier);
  const { data: signals } = useSignals(activeId ?? undefined);

  const leadSearch = useLeadSearch();
  const runSignals = useRunSignals();
  const score = useScoreLeads();
  const patterns = useRunPatterns();

  if (!activeId) {
    return (
      <div className="rounded border border-dashed border-border p-12 text-center">
        <div className="text-sm text-muted-foreground">
          Select an active strategy in the sidebar to load prospects.
        </div>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Stage 2 · Research & scoring"
        title="Prospects"
        subtitle={`Accounts, contacts, and live buying signals for ${active?.product_name ?? "this strategy"}.`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={leadSearch.isPending}
              onClick={() => leadSearch.mutate(activeId)}
              data-testid="button-discover-leads"
            >
              <Search className="mr-2 h-4 w-4" />
              {leadSearch.isPending ? "Searching…" : "Discover leads"}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={runSignals.isPending}
              onClick={() => runSignals.mutate(activeId)}
              data-testid="button-run-signals"
            >
              <Radar className="mr-2 h-4 w-4" />
              {runSignals.isPending ? "Scanning…" : "Run signals"}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={score.isPending}
              onClick={() => score.mutate(activeId)}
              data-testid="button-score"
            >
              <Sparkles className="mr-2 h-4 w-4" />
              {score.isPending ? "Scoring…" : "Score leads"}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={patterns.isPending}
              onClick={() => patterns.mutate(activeId)}
              data-testid="button-patterns"
            >
              <Crosshair className="mr-2 h-4 w-4" />
              {patterns.isPending ? "Clustering…" : "Recognize patterns"}
            </Button>
          </div>
        }
      />

      <Tabs defaultValue="accounts" className="space-y-4">
        <TabsList>
          <TabsTrigger value="accounts">Accounts</TabsTrigger>
          <TabsTrigger value="contacts">Contacts</TabsTrigger>
          <TabsTrigger value="signals">Signals</TabsTrigger>
        </TabsList>

        <TabsContent value="accounts">
          {[1, 2, 3].map((t) => {
            const list =
              t === 1
                ? prioritized?.tier_1
                : t === 2
                  ? prioritized?.tier_2
                  : prioritized?.tier_3;
            return (
              <div key={t} className="mb-5">
                <div className="mb-2 flex items-center gap-3">
                  <TierBadge tier={t} />
                  <span className="text-xs text-muted-foreground">
                    {(list?.length ?? 0)} accounts
                  </span>
                </div>
                <Card className="border-card-border bg-card p-0 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/40">
                      <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                        <th className="px-4 py-2">Company</th>
                        <th className="px-4 py-2">Industry</th>
                        <th className="px-4 py-2 text-right">Employees</th>
                        <th className="px-4 py-2">Revenue</th>
                        <th className="px-4 py-2 text-right">Signals</th>
                        <th className="px-4 py-2">Intent</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {(list ?? []).map((a) => (
                        <tr
                          key={a.id}
                          className="hover-elevate"
                          data-testid={`row-account-${a.id}`}
                        >
                          <td className="px-4 py-2">
                            <div className="flex items-center gap-2">
                              <Building2 className="h-4 w-4 text-muted-foreground" />
                              <div>
                                <div className="font-medium">
                                  {a.company_name}
                                </div>
                                {a.domain && (
                                  <div className="text-[11px] text-muted-foreground">
                                    {a.domain}
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-2 text-muted-foreground">
                            {a.industry || "—"}
                          </td>
                          <td className="px-4 py-2 text-right font-mono tabular-nums">
                            {a.employee_count?.toLocaleString() ?? "—"}
                          </td>
                          <td className="px-4 py-2 text-muted-foreground">
                            {a.revenue_range || "—"}
                          </td>
                          <td className="px-4 py-2 text-right font-mono tabular-nums">
                            {a.signal_count}
                          </td>
                          <td className="px-4 py-2">
                            {a.intent_score !== null && a.intent_score !== undefined ? (
                              <div className="flex items-center gap-2">
                                <span
                                  className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-widest ${
                                    a.intent_classification === "high"
                                      ? "bg-primary/15 text-primary"
                                      : a.intent_classification === "medium"
                                        ? "bg-amber-500/15 text-amber-400"
                                        : "bg-muted text-muted-foreground"
                                  }`}
                                >
                                  {a.intent_classification}
                                </span>
                                <span className="font-mono text-xs tabular-nums">
                                  {a.intent_score.toFixed(0)}
                                </span>
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                      {(!list || list.length === 0) && (
                        <tr>
                          <td
                            colSpan={6}
                            className="px-4 py-6 text-center text-sm text-muted-foreground"
                          >
                            No accounts at this tier.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </Card>
              </div>
            );
          })}
        </TabsContent>

        <TabsContent value="contacts">
          <div className="mb-3 flex items-center gap-3">
            <Select value={tierFilter} onValueChange={setTierFilter}>
              <SelectTrigger className="h-8 w-32 text-xs" data-testid="select-tier">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All tiers</SelectItem>
                <SelectItem value="1">Tier 1</SelectItem>
                <SelectItem value="2">Tier 2</SelectItem>
                <SelectItem value="3">Tier 3</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Card className="border-card-border bg-card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/40">
                <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                  <th className="px-4 py-2">Tier</th>
                  <th className="px-4 py-2">Contact</th>
                  <th className="px-4 py-2">Company</th>
                  <th className="px-4 py-2">Persona</th>
                  <th className="px-4 py-2">ICP fit</th>
                  <th className="px-4 py-2">Signals</th>
                  <th className="px-4 py-2">Engagement</th>
                  <th className="px-4 py-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {contacts?.map((c) => (
                  <tr
                    key={c.id}
                    className="hover-elevate"
                    data-testid={`row-contact-${c.id}`}
                  >
                    <td className="px-4 py-2">
                      <TierBadge tier={c.tier} />
                    </td>
                    <td className="px-4 py-2">
                      <div className="font-medium">
                        {c.full_name}
                        {c.is_demo && (
                          <span className="ml-2">
                            <DemoBadge />
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        {c.title}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">
                      {c.company_name}
                    </td>
                    <td className="px-4 py-2">
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">
                        {c.persona_type ?? "—"}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <ScoreBar value={c.icp_fit_score} color="bg-primary" />
                    </td>
                    <td className="px-4 py-2">
                      <ScoreBar value={c.signal_score} color="bg-amber-500" />
                    </td>
                    <td className="px-4 py-2">
                      <ScoreBar
                        value={c.engagement_score}
                        color="bg-purple-500"
                      />
                    </td>
                    <td className="px-4 py-2 text-right font-mono text-sm tabular-nums">
                      {c.total_score.toFixed(0)}
                    </td>
                  </tr>
                ))}
                {(!contacts || contacts.length === 0) && (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-8 text-center text-sm text-muted-foreground"
                    >
                      No contacts yet. Run lead discovery to populate.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </Card>
        </TabsContent>

        <TabsContent value="signals">
          <Card className="border-card-border bg-card p-5">
            <div className="space-y-2">
              {signals?.map((s) => (
                <div
                  key={s.id}
                  className="flex items-start gap-3 rounded border border-border bg-background/40 p-3"
                  data-testid={`signal-${s.id}`}
                >
                  <div
                    className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                      s.signal_type === "funding"
                        ? "bg-primary"
                        : s.signal_type === "hiring"
                          ? "bg-amber-500"
                          : s.signal_type === "tech"
                            ? "bg-blue-500"
                            : "bg-purple-500"
                    }`}
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                        {s.signal_type}
                      </span>
                      <span className="font-medium">{s.company_name}</span>
                      {s.is_demo && <DemoBadge />}
                      <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                        {fmtRelative(s.detected_at)}
                      </span>
                    </div>
                    <div className="mt-1 text-sm">{s.summary}</div>
                  </div>
                </div>
              ))}
              {(!signals || signals.length === 0) && (
                <div className="rounded border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                  No signals yet. Run signals to detect funding, hiring and
                  tech-stack triggers.
                </div>
              )}
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  );
}
