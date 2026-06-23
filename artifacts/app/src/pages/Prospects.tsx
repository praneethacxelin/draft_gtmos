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
import { useContacts, useUpdateContact, useRevealContactEmail, useRevealContactPhone, useVerifyContactEmail, useVerifyBulkEmails } from "@/hooks/useContacts";
import { useSignals } from "@/hooks/useSignals";
import { useToast } from "@/hooks/use-toast";
import { Checkbox } from "@/components/ui/checkbox";
import {
  useDiscoverExperimentLeads,
  useDiscoverAccounts,
  useGetContacts,
  useCampaignPlan,
  useRunSignals,
  useScoreLeads,
  useRunPatterns,
  useFetchContactEmails,
  useFetchContactPhones,
  type ApolloFacets,
} from "@/hooks/useStrategies";
import { fmtRelative } from "@/lib/format";
import {
  Radar,
  Sparkles,
  Crosshair,
  Building2,
  Pencil,
  X,
  Mail,
  Phone,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ShieldCheck,
  ExternalLink,
  FlaskConical,
  Lock,
  Users,
  Target,
} from "lucide-react";
import { ReasoningPanel, SourceBadge } from "@/components/ReasoningPanel";
import { ApolloFilterGate } from "@/components/ApolloFilterGate";
import { useFetchLimits } from "@/hooks/useSettings";
import { RetriggerBar, type RetriggerAction } from "@/components/RetriggerBar";

interface ContactDraft {
  full_name: string;
  title: string;
  email: string;
  phone: string;
  persona_type: string;
  icp_fit_score: number;
}

const PERSONA_OPTIONS = [
  { value: "_none", label: "— none —" },
  { value: "champion", label: "Champion" },
  { value: "economic_buyer", label: "Economic buyer" },
  { value: "blocker", label: "Blocker" },
];

const FACET_LABELS: Record<string, string> = {
  titles: "Titles",
  seniorities: "Seniorities",
  locations: "Locations",
  industries: "Industries",
  employee_ranges: "Company size",
  technologies: "Technologies",
  keywords: "Keywords",
};

function ExperimentDiscoverySection({ strategyId }: { strategyId: string }) {
  const { data: plan, isLoading } = useCampaignPlan(strategyId);
  const discover = useDiscoverExperimentLeads();
  const [expLimit, setExpLimit] = useState<string>("default");

  if (isLoading) return null;

  if (!plan || !plan.ready) {
    const reason =
      plan?.reason ??
      "Run and analyze a batch of experiments first — discovery uses the winning experiment's facets.";
    return (
      <Card className="mb-4 border-dashed p-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-muted p-2 text-muted-foreground">
            <Lock className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-medium">Experiment-driven discovery (locked)</p>
            <p className="text-sm text-muted-foreground">{reason}</p>
          </div>
        </div>
      </Card>
    );
  }

  const facets = plan.winning_facets ?? {};
  const facetEntries = Object.entries(facets).filter(([, v]) =>
    Array.isArray(v) ? v.length > 0 : Boolean(v),
  );
  const personaSplit = plan.phases?.[0]?.persona_split ?? [];

  function runDiscovery() {
    const limit = expLimit === "default" ? undefined : Number(expLimit);
    discover.mutate({ id: strategyId, limit });
  }

  return (
    <Card className="mb-4 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-primary/10 p-2 text-primary">
            <FlaskConical className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-medium">Experiment-driven discovery</p>
            <p className="text-sm text-muted-foreground">
              Pull leads using the winning experiment
              {plan.winning_experiment_name ? (
                <> — <span className="font-medium text-foreground">{plan.winning_experiment_name}</span></>
              ) : null}{" "}
              and the persona split. These leads are tagged as experiment-sourced for outreach.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={expLimit} onValueChange={setExpLimit}>
            <SelectTrigger className="w-[130px]">
              <SelectValue placeholder="Leads" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="default">Default</SelectItem>
              <SelectItem value="5">5 leads</SelectItem>
              <SelectItem value="10">10 leads</SelectItem>
              <SelectItem value="15">15 leads</SelectItem>
              <SelectItem value="25">25 leads</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={runDiscovery} disabled={discover.isPending}>
            <Target className="mr-2 h-4 w-4" />
            {discover.isPending ? "Discovering…" : "Discover experiment leads"}
          </Button>
        </div>
      </div>

      {facetEntries.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-medium uppercase text-muted-foreground">Winning facets</p>
          <div className="space-y-1.5">
            {facetEntries.map(([key, val]) => {
              const items = Array.isArray(val) ? val : [String(val)];
              return (
                <div key={key} className="flex flex-wrap items-center gap-1.5">
                  <span className="w-24 shrink-0 text-xs text-muted-foreground">
                    {FACET_LABELS[key] ?? key}
                  </span>
                  {items.map((v, i) => (
                    <span
                      key={`${key}-${i}`}
                      className="rounded-full bg-muted px-2 py-0.5 text-xs"
                    >
                      {v}
                    </span>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {personaSplit.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="flex items-center gap-1.5 text-xs font-medium uppercase text-muted-foreground">
            <Users className="h-3.5 w-3.5" /> Persona allocation
          </p>
          <div className="flex flex-wrap gap-2">
            {personaSplit.map((p) => (
              <span
                key={p.persona_type}
                className="rounded-md border px-2 py-1 text-xs"
              >
                <span className="font-medium">{p.label}</span>
                <span className="text-muted-foreground">
                  {" "}
                  · {p.weight_pct}% · {p.prospect_count} leads
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {plan.winning_parameters_insight && (
        <p className="mt-3 text-xs text-muted-foreground">{plan.winning_parameters_insight}</p>
      )}
    </Card>
  );
}

export function Prospects() {
  const { active, activeId } = useActiveStrategy();
  const [tierFilter, setTierFilter] = useState<string>("all");
  const tier = tierFilter === "all" ? undefined : Number(tierFilter);
  const { data: caps } = useFetchLimits();
  const [leadLimit, setLeadLimit] = useState<string>("default");
  const [gateOpen, setGateOpen] = useState(false);
  const [signalLimit, setSignalLimit] = useState<string>("default");

  const { data: prioritized } = usePrioritizedAccounts(activeId ?? undefined);
  const { data: contacts } = useContacts(activeId ?? undefined, tier);
  const { data: signals } = useSignals(activeId ?? undefined);

  const discoverAccounts = useDiscoverAccounts();
  const getContacts = useGetContacts();
  const runSignals = useRunSignals();
  const score = useScoreLeads();
  const patterns = useRunPatterns();
  const fetchEmails = useFetchContactEmails();
  const fetchPhones = useFetchContactPhones();
  const updateContact = useUpdateContact();
  const revealEmail = useRevealContactEmail();
  const revealPhone = useRevealContactPhone();
  const verifyEmail = useVerifyContactEmail();
  const verifyBulk = useVerifyBulkEmails();
  const { toast } = useToast();

  const [selectedContacts, setSelectedContacts] = useState<Set<string>>(new Set());

  const [editingContactId, setEditingContactId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<ContactDraft>({
    full_name: "",
    title: "",
    email: "",
    phone: "",
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
      phone: c.phone ?? "",
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
          phone: editDraft.phone || undefined,
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

  function handleSelectAll(checked: boolean) {
    if (checked && contacts) {
      setSelectedContacts(new Set(contacts.map(c => c.id)));
    } else {
      setSelectedContacts(new Set());
    }
  }

  function handleSelect(id: string, checked: boolean) {
    const next = new Set(selectedContacts);
    if (checked) {
      next.add(id);
    } else {
      next.delete(id);
    }
    setSelectedContacts(next);
  }

  async function handleVerifyBulk() {
    if (selectedContacts.size === 0) return;
    try {
      const res = await verifyBulk.mutateAsync(Array.from(selectedContacts));
      toast({
        title: "Bulk verification complete",
        description: `${res.verified} verified, ${res.invalid} invalid, ${res.catch_all} catch-all.`,
      });
      setSelectedContacts(new Set());
    } catch (err: any) {
      toast({
        title: "Verification failed",
        description: err.message || "An error occurred during verification.",
        variant: "destructive"
      });
    }
  }

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
      <ApolloFilterGate
        open={gateOpen}
        onOpenChange={setGateOpen}
        strategyId={activeId}
        pending={discoverAccounts.isPending}
        confirmLabel="Discover accounts"
        onConfirm={(facets: ApolloFacets) => {
          discoverAccounts.mutate(
            {
              id: activeId,
              limit:
                leadLimit && leadLimit !== "default"
                  ? Number(leadLimit)
                  : undefined,
              facets,
            },
            { onSettled: () => setGateOpen(false) },
          );
        }}
      />
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
              disabled={discoverAccounts.isPending}
              onClick={() => setGateOpen(true)}
              data-testid="button-discover-leads"
            >
              <Building2 className="mr-2 h-4 w-4" />
              {discoverAccounts.isPending ? "Discovering…" : "Discover accounts"}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={getContacts.isPending}
              onClick={() =>
                getContacts.mutate({
                  id: activeId,
                  limit:
                    leadLimit && leadLimit !== "default"
                      ? Number(leadLimit)
                      : undefined,
                })
              }
              title="Pull contacts (people) for the discovered accounts — uses Apollo enrichment credits"
              data-testid="button-get-contacts"
            >
              <Users className="mr-2 h-4 w-4" />
              {getContacts.isPending ? "Pulling…" : "Get contacts"}
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
            <div className="h-5 w-px bg-border" />
            <Button
              size="sm"
              variant="outline"
              disabled={fetchEmails.isPending}
              onClick={() => fetchEmails.mutate(activeId)}
              title="Uses Apollo email credits — only fetches contacts missing an email (up to 20)"
              data-testid="button-fetch-emails"
            >
              <Mail className="mr-2 h-3.5 w-3.5 text-blue-400" />
              {fetchEmails.isPending ? "Fetching…" : "Fetch emails"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={fetchPhones.isPending}
              onClick={() => fetchPhones.mutate(activeId)}
              title="Uses Apollo phone credits — only fetches contacts missing a phone (up to 20)"
              data-testid="button-fetch-phones"
            >
              <Phone className="mr-2 h-3.5 w-3.5 text-emerald-400" />
              {fetchPhones.isPending ? "Fetching…" : "Fetch phones"}
            </Button>
            <div className="h-5 w-px bg-border mx-1" />
            <Button
              size="sm"
              variant="outline"
              disabled={selectedContacts.size === 0 || verifyBulk.isPending}
              onClick={handleVerifyBulk}
              title="Verify emails for selected contacts using Instantly"
              data-testid="button-verify-bulk"
              className={selectedContacts.size > 0 ? "border-primary text-primary hover:text-primary/80" : ""}
            >
              <ShieldCheck className="mr-2 h-3.5 w-3.5" />
              {verifyBulk.isPending ? "Verifying…" : `Verify selected (${selectedContacts.size})`}
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
          source: (prioritized?.tier_1?.some(a => a.source !== 'ai_demo') || 
                   prioritized?.tier_2?.some(a => a.source !== 'ai_demo') || 
                   prioritized?.tier_3?.some(a => a.source !== 'ai_demo')) ? "apollo" : "ai_generated",
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

      {activeId && <ExperimentDiscoverySection strategyId={activeId} />}

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
                        <th className="px-4 py-2">Location</th>
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
                                  <a
                                    href={`https://${a.domain.replace(/^https?:\/\//, '')}`}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex max-w-[220px] items-center gap-1 truncate text-[11px] text-sky-300 hover:text-sky-200"
                                    title={a.domain}
                                  >
                                    <ExternalLink className="h-3 w-3 shrink-0" />
                                    <span className="truncate">{a.domain}</span>
                                  </a>
                                )}
                              </div>
                            </div>
                            {a.tech_stack && a.tech_stack.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1">
                                {a.tech_stack.slice(0, 3).map((tech, i) => (
                                  <span key={i} className="rounded bg-muted/60 px-1.5 py-0.5 text-[9px] text-muted-foreground">
                                    {tech}
                                  </span>
                                ))}
                                {a.tech_stack.length > 3 && (
                                  <span className="rounded bg-muted/40 px-1.5 py-0.5 text-[9px] text-muted-foreground">
                                    +{a.tech_stack.length - 3}
                                  </span>
                                )}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-2 text-muted-foreground text-[11px]">
                            {a.location || "—"}
                          </td>
                          <td className="px-4 py-2 text-muted-foreground text-[11px]">
                            {a.industry || "—"}
                          </td>
                          <td className="px-4 py-2 text-right font-mono tabular-nums">
                            {a.employee_count?.toLocaleString() ?? "—"}
                          </td>
                          <td className="px-4 py-2 text-muted-foreground text-[11px]">
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
                                <SourceBadge source={a.source === "ai_demo" ? "ai_generated" : "apollo"} />
                                {a.source === "ai_demo" && <DemoBadge />}
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
                  <th className="px-4 py-2 w-[40px]">
                    <Checkbox 
                      checked={contacts && contacts.length > 0 && selectedContacts.size === contacts.length}
                      onCheckedChange={handleSelectAll}
                      aria-label="Select all"
                    />
                  </th>
                  <th className="px-4 py-2">Tier</th>
                  <th className="px-4 py-2">Contact</th>
                  <th className="px-4 py-2">Company</th>
                  <th className="px-4 py-2">Email / Phone</th>
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
                        <Checkbox 
                          checked={selectedContacts.has(c.id)}
                          onCheckedChange={(checked) => handleSelect(c.id, checked as boolean)}
                          aria-label={`Select ${c.full_name}`}
                        />
                      </td>
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
                      <td className="px-4 py-2">
                        <div className="max-w-[220px]">
                          <div className="truncate text-muted-foreground" title={c.company_name}>
                            {c.company_name}
                          </div>
                          {c.domain && (
                            <a
                              href={`https://${c.domain.replace(/^https?:\/\//, '')}`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex max-w-full items-center gap-1 truncate text-[11px] text-sky-300 hover:text-sky-200"
                              title={c.domain}
                            >
                              <ExternalLink className="h-3 w-3 shrink-0" />
                              <span className="truncate">{c.domain}</span>
                            </a>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-2">
                        <div className="space-y-0.5">
                          {c.email && c.email !== "(not revealed)" ? (
                            <div className="flex items-center gap-1 text-[11px] text-foreground/80">
                              <Mail className="h-3 w-3 text-blue-400 shrink-0" />
                              <span className="truncate max-w-[140px]" title={c.email}>{c.email}</span>
                              {c.email_verified === "valid" ? (
                                <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0 ml-1" aria-label="Verified (Valid)" />
                              ) : c.email_verified === "invalid" ? (
                                <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0 ml-1" aria-label="Invalid" />
                              ) : c.email_verified === "catch_all" ? (
                                <HelpCircle className="h-3.5 w-3.5 text-yellow-500 shrink-0 ml-1" aria-label="Catch-all" />
                              ) : (
                                <button 
                                  onClick={() => verifyEmail.mutate(c.id, {
                                    onError: (err: any) => {
                                      toast({
                                        title: "Verification failed",
                                        description: err.message || "An error occurred.",
                                        variant: "destructive"
                                      });
                                    }
                                  })}
                                  disabled={verifyEmail.isPending}
                                  className="text-muted-foreground hover:text-foreground transition-colors ml-1"
                                  title="Verify email with Instantly"
                                >
                                  <CheckCircle2 className="h-3.5 w-3.5 opacity-30" />
                                </button>
                              )}
                            </div>
                          ) : c.email === "Not found" ? (
                            <div className="flex items-center gap-1 text-[11px] text-muted-foreground/50">
                              <Mail className="h-3 w-3 shrink-0" />
                              <span>Email unavailable</span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1 text-[11px] text-muted-foreground/50">
                              <Mail className="h-3 w-3 shrink-0" />
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-5 px-1.5 text-[10px]"
                                disabled={revealEmail.isPending}
                                onClick={() => revealEmail.mutate(c.id, {
                                  onSuccess: (data) => {
                                    if (data.email && data.email !== "Not found") {
                                      toast({
                                        title: "Email revealed",
                                        description: `Successfully found email for ${c.full_name}.`,
                                      });
                                    } else if (data.email === "Not found") {
                                      toast({
                                        title: "Email not found",
                                        description: "Apollo matched this contact but does not have their email address.",
                                      });
                                    }
                                  },
                                  onError: (err: any) => {
                                    toast({
                                      title: "Email fetch failed",
                                      description: err.message || "An error occurred fetching the email.",
                                      variant: "destructive"
                                    });
                                  }
                                })}
                                title="Uses 1 Apollo credit to fetch this person's email"
                              >
                                {revealEmail.isPending ? "Fetching..." : "Get Email"}
                              </Button>
                            </div>
                          )}
                          {c.phone && c.phone !== "Not found" && !c.phone.startsWith("Maybe:") ? (
                            <div className="flex items-center gap-1 text-[11px] text-foreground/80">
                              <Phone className="h-3 w-3 text-emerald-400 shrink-0" />
                              <span>{c.phone}</span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1 text-[11px] text-muted-foreground/50">
                              <Phone className="h-3 w-3 shrink-0" />
                              <span>—</span>
                            </div>
                          )}
                        </div>
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
                          colSpan={11}
                          className="bg-muted/30 px-4 py-3"
                        >
                          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
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
                              <Label className="text-xs">Phone</Label>
                              <Input
                                type="tel"
                                placeholder="+1 555 000 0000"
                                value={editDraft.phone}
                                onChange={(e) =>
                                  setEditDraft({
                                    ...editDraft,
                                    phone: e.target.value,
                                  })
                                }
                                className="h-8 text-xs"
                              />
                            </div>
                            <div>
                              <Label className="text-xs">Persona type</Label>
                              <Select
                                value={editDraft.persona_type || "_none"}
                                onValueChange={(v) =>
                                  setEditDraft({
                                    ...editDraft,
                                    persona_type: v === "_none" ? "" : v,
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
                      colSpan={11}
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
