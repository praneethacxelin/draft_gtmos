import { useState } from "react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/PageHeader";
import { TierBadge, ScoreBar, DemoBadge } from "@/components/Pills";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { usePrioritizedAccounts } from "@/hooks/useAccounts";
import { useContacts, useUpdateContact } from "@/hooks/useContacts";
import { useSignals } from "@/hooks/useSignals";
import {
  useLeadSearch,
  useRunSignals,
  useScoreLeads,
  useRunPatterns,
} from "@/hooks/useStrategies";
import { fmtRelative } from "@/lib/format";
import {
  Search,
  Radar,
  Sparkles,
  Crosshair,
  Building2,
  Pencil,
  X,
} from "lucide-react";
import { ReasoningPanel, SourceBadge } from "@/components/ReasoningPanel";
import { useFetchLimits } from "@/hooks/useSettings";
import { RetriggerBar, type RetriggerAction } from "@/components/RetriggerBar";

interface ContactDraft {
  full_name: string;
  title: string;
  email: string;
  persona_type: string;
  icp_fit_score: number;
}

const PERSONA_OPTIONS = [
  { value: "", label: "— none —" },
  { value: "champion", label: "Champion" },
  { value: "economic_buyer", label: "Economic buyer" },
  { value: "blocker", label: "Blocker" },
];

export function Prospects() {
  const { active, activeId } = useActiveStrategy();
  const [tierFilter, setTierFilter] = useState<string>("all");
  const tier = tierFilter === "all" ? undefined : Number(tierFilter);
  const { data: caps } = useFetchLimits();
  const [leadLimit, setLeadLimit] = useState<string>("default");
  const [signalLimit, setSignalLimit] = useState<string>("default");

  const { data: prioritized } = usePrioritizedAccounts(activeId ?? undefined);
  const { data: contacts } = useContacts(activeId ?? undefined, tier);
  const { data: signals } = useSignals(activeId ?? undefined);

  const leadSearch = useLeadSearch();
  const runSignals = useRunSignals();
  const score = useScoreLeads();
  const patterns = useRunPatterns();
  const updateContact = useUpdateContact();

  const [editingContactId, setEditingContactId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<ContactDraft>({
    full_name: "",
    title: "",
    email: "",
    persona_type: "",
    icp_fit_score: 0,
  });
  const [contactDirty, setContactDirty] = useState(false);

  function startEditContact(contactId: string) {
    const c = contacts?.find((x) => x.id === contactId);
    if (!c) return;
    setEditDraft({
      full_name: c.full_name,
      title: c.title ?? "",
      email: c.email ?? "",
      persona_type: c.persona_type ?? "",
      icp_fit_score: c.icp_fit_score,
    });
    setEditingContactId(contactId);
  }

  async function saveContact() {
    if (!editingContactId) return;
    try {
      await updateContact.mutateAsync({
        id: editingContactId,
        data: {
          full_name: editDraft.full_name,
          title: editDraft.title,
          email: editDraft.email || undefined,
          persona_type: editDraft.persona_type || undefined,
          icp_fit_score: editDraft.icp_fit_score,
        },
      });
      setEditingContactId(null);
      setContactDirty(true);
    } catch (err) {
      console.error("Failed to save contact:", err);
    }
  }

  const retriggerActions: RetriggerAction[] = [
    {
      label: score.isPending ? "Scoring…" : "Re-score leads",
      icon: <Sparkles className="h-3 w-3" />,
      onClick: () => activeId && score.mutate(activeId),
      isPending: score.isPending,
    },
    {
      label: patterns.isPending ? "Clustering…" : "Recognize patterns",
      icon: <Crosshair className="h-3 w-3" />,
      onClick: () => activeId && patterns.mutate(activeId),
      isPending: patterns.isPending,
    },
  ];

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
            <Select value={leadLimit} onValueChange={setLeadLimit}>
              <SelectTrigger
                className="h-8 w-28 text-xs"
                data-testid="select-lead-limit"
              >
                <SelectValue
                  placeholder={`Leads: ${caps?.limits.leads_per_run ?? "default"}`}
                />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">
                  Default ({caps?.limits.leads_per_run ?? 5})
                </SelectItem>
                {[3, 5, 10, 15, 25].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} leads
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              variant="secondary"
              disabled={leadSearch.isPending}
              onClick={() =>
                leadSearch.mutate({
                  id: activeId,
                  limit:
                    leadLimit && leadLimit !== "default"
                      ? Number(leadLimit)
                      : undefined,
                })
              }
              data-testid="button-discover-leads"
            >
              <Search className="mr-2 h-4 w-4" />
              {leadSearch.isPending ? "Searching…" : "Discover leads"}
            </Button>
            <Select value={signalLimit} onValueChange={setSignalLimit}>
              <SelectTrigger
                className="h-8 w-32 text-xs"
                data-testid="select-signal-limit"
              >
                <SelectValue
                  placeholder={`Signals/acct: ${caps?.limits.signals_per_account ?? "default"}`}
                />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">
                  Default ({caps?.limits.signals_per_account ?? 3})
                </SelectItem>
                {[2, 3, 5, 10].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} per acct
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              variant="secondary"
              disabled={runSignals.isPending}
              onClick={() =>
                runSignals.mutate({
                  id: activeId,
                  limit:
                    signalLimit && signalLimit !== "default"
                      ? Number(signalLimit)
                      : undefined,
                })
              }
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

      {contactDirty && (
        <RetriggerBar
          message="Contact updated."
          actions={retriggerActions}
          onDismiss={() => setContactDirty(false)}
        />
      )}

      <ReasoningPanel
        title="How prospects are produced"
        fallback={{
          source: "ai_generated",
          logic:
            "Without an Apollo or SerpAPI key, accounts, contacts, and signals are AI-generated demo data. Add live keys in Settings to swap to real Apollo people-search and SerpAPI funding/hiring queries — the per-run limits below cap how many records each click pulls.",
          steps: [
            "Discover leads → Apollo people search (or AI demo) capped by leads_per_run",
            "Run signals → SerpAPI funding + hiring queries (or AI demo) capped by signals_per_account",
            "Score leads → composite ICP fit + signals + engagement + pgvector boost",
          ],
        }}
        className="mb-4"
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
                    {list?.length ?? 0} accounts
                  </span>
                </div>
                <Card className="border-card-border bg-card overflow-hidden p-0">
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
                            {a.intent_score != null ? (
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
                                <SourceBadge source="ai_generated" />
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground">
                                —
                              </span>
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
              <SelectTrigger
                className="h-8 w-32 text-xs"
                data-testid="select-tier"
              >
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
          <Card className="border-card-border bg-card overflow-hidden p-0">
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
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {contacts?.map((c) => (
                  <>
                    <tr
                      key={c.id}
                      className="hover-elevate"
                      data-testid={`row-contact-${c.id}`}
                    >
                      <td className="px-4 py-2">
                        <TierBadge tier={c.tier} />
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex flex-wrap items-center gap-2 font-medium">
                          <span>{c.full_name}</span>
                          <SourceBadge
                            source={c.is_demo ? "ai_generated" : "apollo"}
                          />
                          {c.is_demo && <DemoBadge />}
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
                        <ScoreBar
                          value={c.signal_score}
                          color="bg-amber-500"
                        />
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
                      <td className="px-4 py-2">
                        {editingContactId === c.id ? (
                          <button
                            onClick={() => setEditingContactId(null)}
                            className="rounded p-1 text-muted-foreground hover:text-foreground"
                            title="Cancel"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        ) : (
                          <button
                            onClick={() => startEditContact(c.id)}
                            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                            title="Edit contact"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </td>
                    </tr>
                    {editingContactId === c.id && (
                      <tr key={`edit-${c.id}`}>
                        <td
                          colSpan={9}
                          className="bg-muted/30 px-4 py-3"
                        >
                          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                            <div>
                              <Label className="text-xs">Full name</Label>
                              <Input
                                value={editDraft.full_name}
                                onChange={(e) =>
                                  setEditDraft({
                                    ...editDraft,
                                    full_name: e.target.value,
                                  })
                                }
                                className="h-8 text-xs"
                              />
                            </div>
                            <div>
                              <Label className="text-xs">Title</Label>
                              <Input
                                value={editDraft.title}
                                onChange={(e) =>
                                  setEditDraft({
                                    ...editDraft,
                                    title: e.target.value,
                                  })
                                }
                                className="h-8 text-xs"
                              />
                            </div>
                            <div>
                              <Label className="text-xs">Email</Label>
                              <Input
                                type="email"
                                placeholder="override@company.com"
                                value={editDraft.email}
                                onChange={(e) =>
                                  setEditDraft({
                                    ...editDraft,
                                    email: e.target.value,
                                  })
                                }
                                className="h-8 text-xs"
                              />
                            </div>
                            <div>
                              <Label className="text-xs">Persona type</Label>
                              <Select
                                value={editDraft.persona_type}
                                onValueChange={(v) =>
                                  setEditDraft({
                                    ...editDraft,
                                    persona_type: v,
                                  })
                                }
                              >
                                <SelectTrigger className="h-8 text-xs">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {PERSONA_OPTIONS.map((o) => (
                                    <SelectItem key={o.value} value={o.value}>
                                      {o.label}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <Label className="text-xs">
                                ICP fit score (0–100)
                              </Label>
                              <Input
                                type="number"
                                min={0}
                                max={100}
                                value={editDraft.icp_fit_score}
                                onChange={(e) =>
                                  setEditDraft({
                                    ...editDraft,
                                    icp_fit_score: Number(e.target.value),
                                  })
                                }
                                className="h-8 text-xs"
                              />
                            </div>
                          </div>
                          <div className="mt-3 flex items-center gap-2">
                            <Button
                              size="sm"
                              onClick={saveContact}
                              disabled={updateContact.isPending}
                              className="h-7 text-xs"
                            >
                              {updateContact.isPending
                                ? "Saving…"
                                : "Save changes"}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setEditingContactId(null)}
                              className="h-7 text-xs"
                            >
                              Cancel
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
                {(!contacts || contacts.length === 0) && (
                  <tr>
                    <td
                      colSpan={9}
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
                      <SourceBadge
                        source={s.is_demo ? "ai_generated" : "serpapi"}
                      />
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
