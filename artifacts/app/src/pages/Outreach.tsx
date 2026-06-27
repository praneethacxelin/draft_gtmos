import { useState, useEffect, type ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { PageHeader } from "@/components/PageHeader";
import { TierBadge, StatusPill } from "@/components/Pills";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { useContacts, useVerifyContactEmail, useVerifyBulkEmails } from "@/hooks/useContacts";
import {
  useSequenceByContact,
  useGenerateSequence,
  useDeliverabilityCheck,
  useLaunchSequence,
  useUpdateSequenceStep,
  useSendingAccounts,
  useConnectSendingAccount,
  useToggleWarmup,
  usePauseCampaign,
  useResumeCampaign,
  useWorkspaceCampaigns,
  useLaunchGroup,
  useDisconnectSendingAccount,
  useContactReplies,
  useCampaignLeads,
  useLeadReplies,
} from "@/hooks/useSequences";
import { Mail, Linkedin, Phone, ShieldCheck, Send, Wand2, Pencil, X, FlaskConical, Check, Megaphone, Search, Flame, Plus, Play, Pause, Heart, Loader2, Activity, RefreshCw, Trash2, Code2, Eye, Users, BadgeCheck } from "lucide-react";
import { fmtDate } from "@/lib/format";
import { ReasoningPanel, SourceBadge } from "@/components/ReasoningPanel";
import { RetriggerBar, type RetriggerAction } from "@/components/RetriggerBar";

const SOURCE_META: Record<string, { label: string; icon: typeof FlaskConical }> = {
  experiment: { label: "From experiments", icon: FlaskConical },
  campaign: { label: "From campaigns", icon: Megaphone },
  discovery: { label: "From discovery", icon: Search },
};
const SOURCE_ORDER = ["experiment", "campaign", "discovery"] as const;

type ViewMode = "template" | "preview";

// Substitute lead merge tags ({{firstName}}, {{companyName}}, {{lastName}}) with a
// specific contact's real values — used for the "Preview" view of a template sequence.
function fillMergeTags(text: string, c?: { full_name?: string; company_name?: string } | null): string {
  if (!text) return text;
  const nameParts = (c?.full_name ?? "").trim().split(/\s+/).filter(Boolean);
  const first = nameParts[0] ?? "";
  const last = nameParts.length > 1 ? nameParts.slice(1).join(" ") : "";
  const company = c?.company_name ?? "";
  return text
    .replace(/\{\{\s*(firstName|first_name)\s*\}\}/gi, first || "there")
    .replace(/\{\{\s*(lastName|last_name)\s*\}\}/gi, last)
    .replace(/\{\{\s*(companyName|company_name)\s*\}\}/gi, company || "your company");
}

// Highlight raw variable tokens (e.g. {{firstName}}) in template view
function TemplateText({ text }: { text: string }) {
  const parts = (text ?? "").split(/({{[^}]+}})/g);
  return (
    <span>
      {parts.map((p, i) =>
        /^{{/.test(p) ? (
          <span
            key={i}
            className="rounded bg-primary/15 px-1 py-0.5 font-mono text-[11px] text-primary"
          >
            {p}
          </span>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </span>
  );
}

interface StepDraft {
  subject: string;
  body: string;
  channel: "email" | "linkedin" | "call";
  wait_days: number;
  send_at?: string;
}

export function Outreach() {
  const { active, activeId } = useActiveStrategy();
  const { data: contacts, isFetching: isContactsFetching, refetch: refetchContacts } = useContacts(activeId ?? undefined);
  const [selected, setSelected] = useState<string | null>(null);
  const [stepCount, setStepCount] = useState<number>(4);
  const [viewMode, setViewMode] = useState<ViewMode>("preview");
  const [groupByTitle, setGroupByTitle] = useState<boolean>(false);
  // Multi-select for group generation (checkboxes)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isGeneratingBulk, setIsGeneratingBulk] = useState<boolean>(false);

  useEffect(() => {
    if (!selected && contacts && contacts[0]) setSelected(contacts[0].id);
  }, [contacts, selected]);

  const { data: sequence, isFetching: isSequenceFetching, refetch: refetchSequence } = useSequenceByContact(selected ?? undefined);
  const generate = useGenerateSequence();
  const check = useDeliverabilityCheck();
  const launch = useLaunchSequence();
  const patchStep = useUpdateSequenceStep();
  const pauseCampaign = usePauseCampaign();
  const resumeCampaign = useResumeCampaign();
  const workspaceCampaigns = useWorkspaceCampaigns();
  const launchGroup = useLaunchGroup();
  const verifyEmail = useVerifyContactEmail();
  const verifyBulk = useVerifyBulkEmails();
  const [isVerifying, setIsVerifying] = useState<boolean>(false);

  const contact = contacts?.find((c) => c.id === selected);

  // ── Multi-select helpers ──
  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function setManySelected(ids: string[], on: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => (on ? next.add(id) : next.delete(id)));
      return next;
    });
  }

  // Generate a reusable template sequence (with {{firstName}} merge tags) for every
  // checked contact — or, if none are checked, the currently focused contact.
  async function handleGenerateGroup() {
    const ids = selectedIds.size > 0 ? Array.from(selectedIds) : selected ? [selected] : [];
    if (ids.length === 0) return;
    const dynamic = ids.length > 1; // group → dynamic merge-tag template
    setIsGeneratingBulk(true);
    try {
      for (const id of ids) {
        await generate.mutateAsync({ contactId: id, stepCount, dynamic });
      }
      const { toast } = await import("sonner");
      toast.success(
        ids.length > 1
          ? `Drafted dynamic-variable sequences for ${ids.length} contacts.`
          : "Sequence drafted.",
      );
    } catch (err: any) {
      const { toast } = await import("sonner");
      toast.error(err?.message || "Failed to generate sequences.");
    } finally {
      setIsGeneratingBulk(false);
    }
  }

  // Verify the email of the checked contacts (group) — or, if none are checked,
  // the currently focused contact (single). Uses Instantly first and falls back
  // to Hunter.io (provider="instantly" → the backend tries Instantly, then Hunter).
  async function handleVerifyEmails() {
    const ids = selectedIds.size > 0 ? Array.from(selectedIds) : selected ? [selected] : [];
    if (ids.length === 0) return;
    const { toast } = await import("sonner");
    setIsVerifying(true);
    try {
      if (ids.length === 1) {
        const res = await verifyEmail.mutateAsync({ id: ids[0], provider: "instantly" });
        toast.success(`Email ${res.email_verified ?? "checked"}: ${res.email}`);
      } else {
        const res = await verifyBulk.mutateAsync({ contact_ids: ids, provider: "instantly" });
        toast.success(
          `Verified ${res.total}: ${res.verified} valid · ${res.invalid} invalid · ${res.catch_all} catch-all`,
        );
      }
    } catch (err: any) {
      toast.error(err?.message || "Email verification failed.");
    } finally {
      setIsVerifying(false);
    }
  }

  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<StepDraft>({
    subject: "",
    body: "",
    channel: "email",
    wait_days: 1,
    send_at: undefined,
  });
  const [stepDirty, setStepDirty] = useState(false);

  // ── Global test email — persisted in localStorage ──
  const [testEmail, setTestEmail] = useState<string>(
    () => localStorage.getItem("gtm_test_email") ?? "",
  );
  const [testEmailDraft, setTestEmailDraft] = useState("");
  const [editingTestEmail, setEditingTestEmail] = useState(false);

  // ── Per-lead test email overrides (keyed by contact id) ──
  const [perLeadTestEmail, setPerLeadTestEmail] = useState<Record<string, string>>({});
  const [perLeadEditing, setPerLeadEditing] = useState<Record<string, boolean>>({});
  const [perLeadDraft, setPerLeadDraft] = useState<Record<string, string>>({});

  // Effective test email: per-lead → global → empty (live mode)
  function effectiveTestEmail(contactId: string): string {
    return perLeadTestEmail[contactId] || testEmail || "";
  }

  function openTestEmailEdit() {
    setTestEmailDraft(testEmail);
    setEditingTestEmail(true);
  }

  function saveTestEmail() {
    const val = testEmailDraft.trim();
    setTestEmail(val);
    if (val) {
      localStorage.setItem("gtm_test_email", val);
    } else {
      localStorage.removeItem("gtm_test_email");
    }
    setEditingTestEmail(false);
  }

  function clearTestEmail() {
    setTestEmail("");
    localStorage.removeItem("gtm_test_email");
  }

  function startEditStep(stepId: string) {
    const step = sequence?.steps.find((s) => s.id === stepId);
    if (!step) return;
    
    // Convert to datetime-local format (YYYY-MM-DDThh:mm)
    let send_at_local = undefined;
    if (step.send_at) {
      const dt = new Date(step.send_at);
      if (!isNaN(dt.getTime())) {
        send_at_local = new Date(dt.getTime() - (dt.getTimezoneOffset() * 60000)).toISOString().slice(0, 16);
      }
    }

    setEditDraft({
      subject: step.subject ?? "",
      body: step.body ?? "",
      channel: step.channel as "email" | "linkedin" | "call",
      wait_days: step.wait_days,
      send_at: send_at_local,
    });
    setEditingStepId(stepId);
  }

  async function saveStep() {
    if (!editingStepId) return;
    try {
      const dataToSave = { ...editDraft };
      // Convert datetime-local back to ISO UTC string if set
      if (dataToSave.send_at) {
        dataToSave.send_at = new Date(dataToSave.send_at).toISOString();
      }
      await patchStep.mutateAsync({ id: editingStepId, data: dataToSave });
      setEditingStepId(null);
      setStepDirty(true);
    } catch (err) {
      console.error("Failed to save step:", err);
    }
  }

  const retriggerActions: RetriggerAction[] = [
    {
      label: check.isPending ? "Checking…" : "Check deliverability",
      icon: <ShieldCheck className="h-3 w-3" />,
      onClick: () => sequence && check.mutate(sequence.id),
      isPending: check.isPending,
    },
    {
      label: generate.isPending ? "Generating…" : "Regenerate sequence",
      icon: <Wand2 className="h-3 w-3" />,
      onClick: () => selected && generate.mutate({ contactId: selected, stepCount }),
      isPending: generate.isPending,
    },
  ];

  // ── Timezone normalisation (must be before early return — used in useState init) ──
  const TZ_ALIASES: Record<string, string> = {
    "Asia/Calcutta":  "Asia/Kolkata",
    "US/Eastern":     "America/New_York",
    "US/Central":     "America/Chicago",
    "US/Mountain":    "America/Denver",
    "US/Pacific":     "America/Los_Angeles",
    "US/Alaska":      "America/Anchorage",
    "US/Hawaii":      "Pacific/Honolulu",
    "US/Arizona":     "America/Phoenix",
    "Etc/UTC":        "UTC",
    "Etc/GMT":        "UTC",
    "GMT":            "UTC",
    "GB":             "Europe/London",
    "Japan":          "Asia/Tokyo",
    "Singapore":      "Asia/Singapore",
  };
  const rawBrowserTz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const browserTz = TZ_ALIASES[rawBrowserTz] ?? rawBrowserTz;

  const presetTzs = [
    "UTC",
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Phoenix", "America/Toronto", "America/Sao_Paulo",
    "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Moscow",
    "Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Asia/Tokyo", "Asia/Shanghai",
    "Australia/Sydney", "Pacific/Auckland",
  ];

  // ── Schedule — persisted in localStorage so navigation doesn't reset it ──
  // IMPORTANT: this useState MUST be before any conditional return to satisfy React's hooks rules.
  const SCHED_KEY = "gtm_launch_schedule";
  const [schedule, setSchedule] = useState(() => {
    try {
      const saved = localStorage.getItem(SCHED_KEY);
      if (saved) return JSON.parse(saved);
    } catch {}
    return {
      timezone: TZ_ALIASES[Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"] ??
                (Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"),
      time_from: "09:00",
      time_to: "17:00",
      days: { "0": false, "1": true, "2": true, "3": true, "4": true, "5": true, "6": false },
    };
  });

  function updateSchedule(patch: Partial<typeof schedule>) {
    const next = { ...schedule, ...patch };
    setSchedule(next);
    try { localStorage.setItem(SCHED_KEY, JSON.stringify(next)); } catch {}
  }

  const toggleDay = (d: string) => {
    const next = { ...schedule, days: { ...schedule.days, [d]: !schedule.days[d as keyof typeof schedule.days] } };
    setSchedule(next);
    try { localStorage.setItem(SCHED_KEY, JSON.stringify(next)); } catch {}
  };

  const daysMap = [
    { k: "1", label: "M" },
    { k: "2", label: "T" },
    { k: "3", label: "W" },
    { k: "4", label: "T" },
    { k: "5", label: "F" },
    { k: "6", label: "S" },
    { k: "0", label: "S" },
  ];

  if (!activeId) {
    return (
      <div className="rounded border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        Select an active strategy to plan outreach.
      </div>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Stage 3 · 3-channel outreach"
        title="Outreach"
        subtitle={`Persona-aware sequences for all contacts in ${active?.product_name ?? ""}, ranked by tier and score.`}
      />

      {stepDirty && (
        <RetriggerBar
          message="Step updated."
          actions={retriggerActions}
          onDismiss={() => setStepDirty(false)}
        />
      )}

      {/* Campaign Settings banner */}
      <div className="mb-4 rounded-lg border border-border bg-card p-4 space-y-4 shadow-sm">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-amber-500/15 text-amber-400">
            <FlaskConical className="h-4 w-4 shrink-0" />
          </span>
          <div className="min-w-0">
            <div className="text-sm font-semibold leading-tight">Launch Settings</div>
            <div className="text-[11px] text-muted-foreground">Test recipient, timezone and sending window applied to every launch.</div>
          </div>
        </div>
        
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Test Email (Optional)</Label>
            {editingTestEmail ? (
              <div className="flex items-center gap-2">
                <Input
                  value={testEmailDraft}
                  onChange={(e) => setTestEmailDraft(e.target.value)}
                  placeholder="you@yourcompany.com"
                  className="h-8 text-xs"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveTestEmail();
                    if (e.key === "Escape") setEditingTestEmail(false);
                  }}
                />
                <Button size="sm" className="h-8 px-2" onClick={saveTestEmail}>
                  <Check className="h-4 w-4" />
                </Button>
                <Button size="sm" variant="ghost" className="h-8 px-2" onClick={() => setEditingTestEmail(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2 h-8">
                {testEmail ? (
                  <span className="rounded bg-amber-500/15 px-2 py-1 font-mono text-xs text-amber-500">
                    {testEmail}
                  </span>
                ) : (
                  <span className="text-xs italic text-muted-foreground">Live sending mode</span>
                )}
                <button onClick={openTestEmailEdit} className="text-muted-foreground hover:text-foreground">
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                {testEmail && (
                  <button onClick={clearTestEmail} className="text-muted-foreground hover:text-destructive">
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Timezone</Label>
            <Select value={schedule.timezone} onValueChange={(v) => updateSchedule({ timezone: v })}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {presetTzs.map(tz => (
                  <SelectItem key={tz} value={tz}>{tz}</SelectItem>
                ))}
                {!presetTzs.includes(browserTz) && (
                  <SelectItem value={browserTz}>{browserTz} (Local)</SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Sending Window</Label>
            <div className="flex items-center gap-2">
              <Input 
                type="time" 
                value={schedule.time_from} 
                onChange={(e) => updateSchedule({ time_from: e.target.value })}
                className="h-8 text-xs w-[100px]" 
              />
              <span className="text-muted-foreground text-xs">to</span>
              <Input 
                type="time" 
                value={schedule.time_to} 
                onChange={(e) => updateSchedule({ time_to: e.target.value })}
                className="h-8 text-xs w-[100px]" 
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Active Days</Label>
            <div className="flex items-center gap-1">
              {daysMap.map(d => (
                <button
                  key={d.k}
                  onClick={() => toggleDay(d.k)}
                  className={`h-8 w-8 rounded text-xs font-medium transition-colors ${
                    schedule.days[d.k as keyof typeof schedule.days]
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-3 space-y-4">
          <Card className="rounded-lg border-card-border bg-card p-3 shadow-sm">
            <div className="mb-2 px-2 flex items-center justify-between text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
              <span>Contacts{selectedIds.size > 0 ? ` (${selectedIds.size} selected)` : ""}</span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setGroupByTitle((v) => !v)}
                  className={`flex items-center gap-1 rounded px-1.5 py-0.5 transition-colors ${
                    groupByTitle
                      ? "bg-primary/15 text-primary"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                  title="Group leads by similar job title"
                >
                  <Users className="h-3 w-3" /> Similar
                </button>
                <button
                  onClick={() => refetchContacts()}
                  className="text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded"
                  title="Refresh contacts"
                  disabled={isContactsFetching}
                >
                  <RefreshCw className={`h-3 w-3 ${isContactsFetching ? "animate-spin" : ""}`} />
                </button>
              </div>
            </div>
            <div className="space-y-3">
              {(() => {
                const renderContactRow = (c: NonNullable<typeof contacts>[number]) => (
                  <div
                    key={c.id}
                    onClick={() => {
                      setSelected(c.id);
                      setEditingStepId(null);
                      setStepDirty(false);
                    }}
                    className={`flex w-full cursor-pointer items-center gap-2 rounded px-2 py-2 text-left text-sm hover-elevate ${
                      selected === c.id ? "bg-sidebar-accent" : ""
                    } ${selectedIds.has(c.id) ? "ring-1 ring-primary/40" : ""}`}
                    data-testid={`contact-row-${c.id}`}
                  >
                    <Checkbox
                      checked={selectedIds.has(c.id)}
                      onCheckedChange={() => toggleSelect(c.id)}
                      onClick={(e) => e.stopPropagation()}
                      className="h-4 w-4 shrink-0"
                      aria-label={`Select ${c.full_name}`}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">
                        {c.full_name}
                      </div>
                      <div className="truncate text-[11px] text-muted-foreground">
                        {c.title} · {c.company_name}
                      </div>
                    </div>
                    {c.email_verified && (
                      <span
                        title={`Email: ${c.email_verified}`}
                        className={`shrink-0 h-2 w-2 rounded-full ${
                          c.email_verified === "valid"
                            ? "bg-emerald-500"
                            : c.email_verified === "invalid"
                              ? "bg-red-500"
                              : c.email_verified === "catch_all"
                                ? "bg-amber-500"
                                : "bg-muted-foreground/50"
                        }`}
                      />
                    )}
                    <TierBadge tier={c.tier} />
                  </div>
                );

                const groupHeader = (
                  label: ReactNode,
                  items: NonNullable<typeof contacts>,
                ) => {
                  const ids = items.map((c) => c.id);
                  const allOn = ids.length > 0 && ids.every((id) => selectedIds.has(id));
                  return (
                    <div className="flex items-center gap-1.5 px-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                      <Checkbox
                        checked={allOn}
                        onCheckedChange={(v) => setManySelected(ids, !!v)}
                        className="h-3.5 w-3.5 shrink-0"
                        aria-label="Select group"
                      />
                      {label}
                      <span className="text-muted-foreground/70">({items.length})</span>
                    </div>
                  );
                };

                if (groupByTitle) {
                  const titleGroups: Record<string, NonNullable<typeof contacts>> = {};
                  for (const c of contacts ?? []) {
                    const key = (c.title ?? "").trim() || "No title";
                    (titleGroups[key] ??= []).push(c);
                  }
                  const entries = Object.entries(titleGroups).sort(
                    (a, b) => b[1].length - a[1].length,
                  );
                  return entries.map(([title, items]) => (
                    <div key={title} className="space-y-1">
                      {groupHeader(
                        <span className="flex items-center gap-1">
                          <Users className="h-3 w-3" />
                          {title}
                        </span>,
                        items,
                      )}
                      {items.map(renderContactRow)}
                    </div>
                  ));
                }

                return SOURCE_ORDER.map((src) => {
                  const group = (contacts ?? []).filter(
                    (c) => (c.source ?? "discovery") === src,
                  );
                  if (group.length === 0) return null;
                  const meta = SOURCE_META[src];
                  const Icon = meta.icon;
                  return (
                    <div key={src} className="space-y-1">
                      {groupHeader(
                        <span className="flex items-center gap-1">
                          <Icon className="h-3 w-3" />
                          {meta.label}
                        </span>,
                        group,
                      )}
                      {group.map(renderContactRow)}
                    </div>
                  );
                });
              })()}
              {(!contacts || contacts.length === 0) && (
                <div className="px-3 py-6 text-center text-xs text-muted-foreground">
                  No contacts yet. Run lead discovery first.
                </div>
              )}
            </div>
          </Card>
        </div>

        <div className="lg:col-span-5 space-y-4">
          <Card className="border-card-border bg-card p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-base font-semibold">
                    {contact?.full_name ?? "Select a contact"}
                  </span>
                  {contact && (
                    <button 
                      onClick={() => refetchSequence()} 
                      className="text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded"
                      title="Refresh sequence"
                      disabled={isSequenceFetching}
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${isSequenceFetching ? "animate-spin" : ""}`} />
                    </button>
                  )}
                </div>
                {contact && (
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {contact.title} · {contact.company_name}
                  </div>
                )}
                {/* ── Per-lead test email override ── */}
                {contact && (
                  <div className="mt-2 flex items-center gap-2">
                    <FlaskConical className="h-3 w-3 shrink-0 text-amber-400" />
                    <span className="text-[11px] text-muted-foreground">Test email:</span>
                    {perLeadEditing[contact.id] ? (
                      <>
                        <Input
                          value={perLeadDraft[contact.id] ?? ""}
                          onChange={(e) => setPerLeadDraft(p => ({ ...p, [contact.id]: e.target.value }))}
                          placeholder={testEmail || "override@yourdomain.com"}
                          className="h-6 w-44 text-[11px] border-amber-500/40 focus:border-amber-500"
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              setPerLeadTestEmail(p => ({ ...p, [contact.id]: perLeadDraft[contact.id]?.trim() ?? "" }));
                              setPerLeadEditing(p => ({ ...p, [contact.id]: false }));
                            }
                            if (e.key === "Escape") setPerLeadEditing(p => ({ ...p, [contact.id]: false }));
                          }}
                        />
                        <button className="text-amber-400 hover:text-amber-300" onClick={() => {
                          setPerLeadTestEmail(p => ({ ...p, [contact.id]: perLeadDraft[contact.id]?.trim() ?? "" }));
                          setPerLeadEditing(p => ({ ...p, [contact.id]: false }));
                        }}><Check className="h-3 w-3" /></button>
                        <button className="text-muted-foreground" onClick={() => setPerLeadEditing(p => ({ ...p, [contact.id]: false }))}>
                          <X className="h-3 w-3" />
                        </button>
                      </>
                    ) : (
                      <>
                        {perLeadTestEmail[contact.id] ? (
                          <span className="rounded bg-amber-500/15 px-1.5 py-0.5 font-mono text-[11px] text-amber-400">{perLeadTestEmail[contact.id]}</span>
                        ) : testEmail ? (
                          <span className="rounded bg-amber-500/10 px-1.5 py-0.5 font-mono text-[11px] text-amber-500/70 italic">{testEmail} (global)</span>
                        ) : (
                          <span className="text-[11px] italic text-muted-foreground">not set</span>
                        )}
                        <button className="text-muted-foreground hover:text-amber-400 transition-colors" title="Set per-lead test email"
                          onClick={() => {
                            setPerLeadDraft(p => ({ ...p, [contact.id]: perLeadTestEmail[contact.id] ?? "" }));
                            setPerLeadEditing(p => ({ ...p, [contact.id]: true }));
                          }}>
                          <Pencil className="h-3 w-3" />
                        </button>
                        {perLeadTestEmail[contact.id] && (
                          <button className="text-muted-foreground hover:text-destructive transition-colors" title="Clear"
                            onClick={() => setPerLeadTestEmail(p => ({ ...p, [contact.id]: "" }))}>
                            <X className="h-3 w-3" />
                          </button>
                        )}
                      </>
                    )}
                  </div>
                )}
                {sequence && (
                  <div className="mt-2 flex items-center gap-2">
                    <StatusPill status={sequence.status} />
                    {sequence.instantly_campaign_id && (
                      <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-primary">
                        Active via Instantly
                      </span>
                    )}
                    {sequence.status === "simulated" && (
                      <span className="rounded bg-purple-500/15 px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-purple-400">
                        Simulated (no Instantly key)
                      </span>
                    )}
                  </div>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/60 bg-muted/30 p-2">
                <Select value={String(stepCount)} onValueChange={(v) => setStepCount(Number(v))}>
                  <SelectTrigger className="h-9 w-[140px] text-xs">
                    <SelectValue placeholder="Sequence Length" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="4">4 Steps (Default)</SelectItem>
                    <SelectItem value="5">5 Steps (Extra Li)</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={(selectedIds.size === 0 && !selected) || generate.isPending || isGeneratingBulk}
                  onClick={handleGenerateGroup}
                  data-testid="button-generate-sequence"
                  title={
                    selectedIds.size > 1
                      ? `Generate a reusable dynamic-variable template for ${selectedIds.size} selected contacts`
                      : "Generate a sequence for the selected contact"
                  }
                >
                  <Wand2 className="mr-2 h-4 w-4" />
                  {generate.isPending || isGeneratingBulk
                    ? "Generating…"
                    : selectedIds.size > 1
                      ? `Generate (${selectedIds.size})`
                      : "Generate"}
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={(selectedIds.size === 0 && !selected) || isVerifying}
                  onClick={handleVerifyEmails}
                  data-testid="button-verify-email"
                  title={
                    selectedIds.size > 1
                      ? `Verify ${selectedIds.size} emails (Instantly, then Hunter.io fallback)`
                      : "Verify this contact's email (Instantly, then Hunter.io fallback)"
                  }
                >
                  <BadgeCheck className="mr-2 h-4 w-4" />
                  {isVerifying
                    ? "Verifying…"
                    : selectedIds.size > 1
                      ? `Verify (${selectedIds.size})`
                      : "Verify Email"}
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!sequence || check.isPending}
                  onClick={() => sequence && check.mutate(sequence.id)}
                  data-testid="button-deliverability"
                >
                  <ShieldCheck className="mr-2 h-4 w-4" />
                  {check.isPending ? "Checking…" : "Deliverability"}
                </Button>
                <div className="mx-1 hidden h-6 w-px self-center bg-border sm:block" aria-hidden />
                {/* Test Launch — sends to test email, keeps sequence as draft */}
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!sequence || launch.isPending || !effectiveTestEmail(selected ?? "")}
                  onClick={() => {
                    if (!sequence || !selected) return;
                    const addr = effectiveTestEmail(selected);
                    if (!addr) return;
                    launch.mutate({ sequenceId: sequence.id, testEmail: addr, schedule, is_test: true });
                  }}
                  data-testid="button-test-launch"
                  title={
                    effectiveTestEmail(selected ?? "")
                      ? `Test send → ${effectiveTestEmail(selected ?? "")} (sequence stays draft)`
                      : "Set a test email above to enable test launch"
                  }
                  className="border-amber-500/50 text-amber-400 hover:bg-amber-500/10 hover:text-amber-300 disabled:opacity-40"
                >
                  <FlaskConical className="mr-2 h-4 w-4" />
                  {launch.isPending ? "Sending…" : "Test Launch"}
                </Button>
                {/* Live Launch — sends to lead's actual email, sets sequence active */}
                <Button
                  size="sm"
                  disabled={!sequence || launch.isPending}
                  onClick={() => sequence && launch.mutate({ sequenceId: sequence.id, testEmail: undefined, schedule, is_test: false })}
                  data-testid="button-launch"
                  title="Launch to real lead email via Instantly"
                >
                  <Send className="mr-2 h-4 w-4" />
                  {launch.isPending ? "Launching…" : "Launch"}
                </Button>
                {/* Group Launch — ONE campaign with all selected contacts as leads */}
                {selectedIds.size > 1 && (
                  <Button
                    size="sm"
                    disabled={!sequence || launchGroup.isPending}
                    onClick={() =>
                      sequence &&
                      launchGroup.mutate({
                        contact_ids: Array.from(selectedIds),
                        template_sequence_id: sequence.id,
                        schedule,
                        is_test: false,
                      })
                    }
                    data-testid="button-launch-group"
                    title={`Create ONE campaign with the ${selectedIds.size} selected contacts as leads (dynamic variables, schedule & sending accounts included)`}
                    className="bg-emerald-600 text-white hover:bg-emerald-600/90"
                  >
                    <Users className="mr-2 h-4 w-4" />
                    {launchGroup.isPending ? "Launching…" : `Launch Group (${selectedIds.size})`}
                  </Button>
                )}
              </div>
            </div>

            {sequence?.deliverability_report && (
              <div className="mt-4 rounded border border-border bg-background/40 p-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs uppercase tracking-widest text-muted-foreground">
                    Deliverability
                  </div>
                  <div
                    className={`font-mono text-sm tabular-nums ${
                      (sequence.deliverability_score ?? 0) >= 80
                        ? "text-primary"
                        : "text-amber-400"
                    }`}
                  >
                    {sequence.deliverability_score?.toFixed(0)} / 100
                  </div>
                </div>
                {(sequence.deliverability_report.flagged_phrases?.length ?? 0) >
                  0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {sequence.deliverability_report.flagged_phrases!.map(
                      (p: string, i: number) => (
                        <span
                          key={i}
                          className="rounded bg-destructive/10 px-1.5 py-0.5 text-[10px] text-destructive"
                        >
                          {p}
                        </span>
                      ),
                    )}
                  </div>
                )}
              </div>
            )}
          </Card>

          {sequence ? (
            <div className="space-y-3">
              <ReasoningPanel
                provenance={sequence.provenance ?? undefined}
                fallback={{
                  source: "ai_generated",
                  logic: `4-step ${sequence.steps.some((s) => s.channel === "linkedin" && s.step_number === 1) ? "LinkedIn-first" : "email-first"} sequence generated by the model from the contact's persona profile and the strategy's top use cases.`,
                  steps: [
                    "Pick channel order based on contact seniority",
                    "Prompt model for per-step subject + body",
                    "Schedule send_at timestamps with cumulative wait days",
                  ],
                }}
              />
              <div className="flex items-center justify-between gap-2">
                <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Sequence Preview
                </div>
                <div className="inline-flex overflow-hidden rounded border border-border text-[10px]">
                  <button
                    onClick={() => setViewMode("template")}
                    className={`flex items-center gap-1 px-2.5 py-1.5 ${
                      viewMode === "template"
                        ? "bg-muted text-foreground"
                        : "text-muted-foreground hover:bg-muted/50"
                    }`}
                  >
                    <Code2 className="h-3 w-3" /> Template
                  </button>
                  <button
                    onClick={() => setViewMode("preview")}
                    className={`flex items-center gap-1 px-2.5 py-1.5 ${
                      viewMode === "preview"
                        ? "bg-muted text-foreground"
                        : "text-muted-foreground hover:bg-muted/50"
                    }`}
                  >
                    <Eye className="h-3 w-3" /> Preview
                  </button>
                </div>
              </div>
              {viewMode === "template" && (
                <div className="rounded border border-dashed border-border bg-background/40 px-3 py-2 text-[11px] text-muted-foreground">
                  <strong>Template View</strong> — raw variables shown. Switch to Preview to see personalized content.
                </div>
              )}
              {sequence.steps.map((s) => (
                <Card
                  key={s.id}
                  className="border-card-border bg-card p-4"
                  data-testid={`step-${s.step_number}`}
                >
                  <div className="mb-3 flex items-center gap-3">
                    <div
                      className={`flex h-8 w-8 items-center justify-center rounded ${
                        s.channel === "email"
                          ? "bg-primary/15 text-primary"
                          : s.channel === "linkedin"
                            ? "bg-blue-500/15 text-blue-400"
                            : "bg-amber-500/15 text-amber-400"
                      }`}
                    >
                      {s.channel === "email" ? (
                        <Mail className="h-4 w-4" />
                      ) : s.channel === "linkedin" ? (
                        <Linkedin className="h-4 w-4" />
                      ) : (
                        <Phone className="h-4 w-4" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-muted-foreground">
                        <span>
                          Step {s.step_number} · {editingStepId === s.id ? editDraft.channel : s.channel}
                        </span>
                        <SourceBadge source="ai_generated" />
                      </div>
                      {editingStepId !== s.id && (
                        <div className="text-sm font-medium">
                          {s.subject ? (
                            viewMode === "template" ? (
                              <TemplateText text={s.subject} />
                            ) : (
                              fillMergeTags(s.subject, contact)
                            )
                          ) : s.channel === "call" ? (
                            "Call talking points"
                          ) : (
                            "(no subject)"
                          )}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {editingStepId !== s.id && (
                        <div className="text-right text-[11px] text-muted-foreground">
                          Wait {s.wait_days}d · {fmtDate(s.send_at)}
                        </div>
                      )}
                      {editingStepId === s.id ? (
                        <button
                          onClick={() => setEditingStepId(null)}
                          className="rounded p-1 text-muted-foreground hover:text-foreground"
                          title="Cancel edit"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      ) : (
                        <button
                          onClick={() => startEditStep(s.id)}
                          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                          title="Edit step"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  {editingStepId === s.id ? (
                    <div className="space-y-3 border-t border-border pt-3">
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-2">
                        <div>
                          <Label className="text-xs">Channel</Label>
                          <Select
                            value={editDraft.channel}
                            onValueChange={(v) =>
                              setEditDraft({ ...editDraft, channel: v as "email" | "linkedin" | "call" })
                            }
                          >
                            <SelectTrigger className="h-8 text-xs">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="email">Email</SelectItem>
                              <SelectItem value="linkedin">LinkedIn</SelectItem>
                              <SelectItem value="call">Call</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs">Wait days</Label>
                          <Input
                            type="number"
                            min={0}
                            value={editDraft.wait_days}
                            onChange={(e) =>
                              setEditDraft({
                                ...editDraft,
                                wait_days: Number(e.target.value),
                              })
                            }
                            className="h-8 text-xs"
                          />
                        </div>
                      </div>
                      {editDraft.channel !== "call" && (
                        <div>
                          <Label className="text-xs">Subject</Label>
                          <Input
                            value={editDraft.subject}
                            onChange={(e) =>
                              setEditDraft({
                                ...editDraft,
                                subject: e.target.value,
                              })
                            }
                            className="text-sm"
                          />
                        </div>
                      )}
                      <div>
                        <Label className="text-xs">Body</Label>
                        <Textarea
                          value={editDraft.body}
                          rows={7}
                          onChange={(e) =>
                            setEditDraft({
                              ...editDraft,
                              body: e.target.value,
                            })
                          }
                          className="text-sm"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          onClick={saveStep}
                          disabled={patchStep.isPending}
                          className="h-7 text-xs"
                        >
                          {patchStep.isPending ? "Saving…" : "Save changes"}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setEditingStepId(null)}
                          className="h-7 text-xs"
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="whitespace-pre-wrap rounded border border-border bg-background/40 p-3 text-sm text-foreground/90">
                      {viewMode === "template" ? (
                        <TemplateText text={s.body || "—"} />
                      ) : (
                        fillMergeTags(s.body || "—", contact)
                      )}
                    </div>
                  )}
                </Card>
              ))}
            </div>
          ) : (
            <div className="rounded border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              No sequence drafted yet. Click Generate to draft a 4-step plan.
            </div>
          )}
        </div>

        <div className="lg:col-span-4 space-y-4">
          <CampaignsListCard 
            sequence={sequence} 
            campaigns={workspaceCampaigns.data}
            contactId={selected ?? undefined}
            onPause={(id) => pauseCampaign.mutate(id)}
            onResume={(id) => resumeCampaign.mutate(id)}
            isPausing={pauseCampaign.isPending}
            isResuming={resumeCampaign.isPending}
            isFetching={workspaceCampaigns.isFetching}
            onRefresh={() => workspaceCampaigns.refetch()}
          />
          <SendingAccounts />
        </div>
      </div>
    </>
  );
}

function SendingAccounts() {
  const { data: accounts, isLoading, isFetching, refetch, error } = useSendingAccounts();
  const connect = useConnectSendingAccount();
  const toggleWarmup = useToggleWarmup();
  const disconnect = useDisconnectSendingAccount();

  const [showConnectModal, setShowConnectModal] = useState(false);
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [providerCode, setProviderCode] = useState<number>(2); // Gmail default
  const [appPassword, setAppPassword] = useState("");
  
  // Custom IMAP/SMTP details
  const [imapHost, setImapHost] = useState("");
  const [imapPort, setImapPort] = useState<number>(993);
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState<number>(465);

  const [connectError, setConnectError] = useState("");

  const handleConnect = async (e: any) => {
    e.preventDefault();
    setConnectError("");
    try {
      await connect.mutateAsync({
        email,
        first_name: firstName,
        last_name: lastName,
        provider_code: providerCode,
        app_password: appPassword,
        ...(providerCode === 1 ? {
          imap_host: imapHost,
          imap_port: Number(imapPort),
          smtp_host: smtpHost,
          smtp_port: Number(smtpPort)
        } : {})
      });
      // Reset form
      setEmail("");
      setFirstName("");
      setLastName("");
      setAppPassword("");
      setImapHost("");
      setImapPort(993);
      setSmtpHost("");
      setSmtpPort(465);
      setShowConnectModal(false);
      import("sonner").then(({ toast }) => {
        toast.success("Account connected successfully!");
      });
    } catch (err: any) {
      setConnectError(err.message || "Failed to connect account. Verify credentials.");
    }
  };

  const handleToggleWarmup = async (accEmail: string, currentStatus: number) => {
    const nextEnable = currentStatus === 0;
    try {
      await toggleWarmup.mutateAsync({ email: accEmail, enable: nextEnable });
      import("sonner").then(({ toast }) => {
        toast.success(`Warmup ${nextEnable ? "started" : "paused"} for ${accEmail}`);
      });
    } catch (err: any) {
      import("sonner").then(({ toast }) => {
        toast.error(err.message || "Failed to update warmup status.");
      });
    }
  };

  return (
    <>
      <Card className="border-card-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold">Sending Accounts</span>
            <button 
              onClick={() => refetch()} 
              className="text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded"
              title="Refresh sending accounts"
              disabled={isFetching}
            >
              <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
            </button>
          </div>
          <Button size="sm" variant="outline" className="h-7 px-2" onClick={() => setShowConnectModal(true)}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            Connect
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-6 text-xs text-muted-foreground">
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            Loading sending accounts...
          </div>
        ) : error ? (
          <div className="rounded border border-destructive/40 bg-destructive/10 p-4 text-center text-xs text-destructive">
            <div className="font-semibold">Instantly API error</div>
            <div className="mt-1 text-destructive/90">{(error as Error).message}</div>
            <div className="mt-2 text-[10px] text-muted-foreground">
              The account/warmup/campaign features require an Instantly workspace with an
              active paid plan (or active trial). The API key authenticates, but Instantly
              rejects data access for this workspace.
            </div>
          </div>
        ) : !accounts || accounts.length === 0 ? (
          <div className="rounded border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
            No sending accounts connected. Click Connect to link an email inbox via App Password.
          </div>
        ) : (
          <div className="space-y-3">
            {accounts.map((acc) => {
              const warmupActive = acc.warmup_status === 1;
              const health = acc.health_score ?? 100;
              const isGmail = acc.provider_code === 2;
              const isOutlook = acc.provider_code === 3;
              
              let providerLabel = "Custom";
              if (isGmail) providerLabel = "Gmail";
              if (isOutlook) providerLabel = "Outlook";

              return (
                <div key={acc.email} className="rounded border border-border bg-background/30 p-3 space-y-2.5 text-foreground">
                  <div className="flex items-start justify-between gap-1">
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-xs truncate" title={acc.email}>
                        {acc.email}
                      </div>
                      <div className="text-[10px] text-muted-foreground truncate">
                        {acc.first_name} {acc.last_name} · <span className="underline">{providerLabel}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Button
                        size="sm"
                        variant={warmupActive ? "default" : "outline"}
                        className={`h-7 px-2.5 ${warmupActive ? "bg-amber-500 hover:bg-amber-600 text-white border-transparent" : ""}`}
                        onClick={() => handleToggleWarmup(acc.email, acc.warmup_status)}
                        disabled={toggleWarmup.isPending}
                      >
                        {warmupActive ? (
                          <>
                            <Flame className="mr-1 h-3.5 w-3.5 animate-pulse text-red-100" />
                            Warmup Active
                          </>
                        ) : (
                          <>
                            <Play className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
                            Start Warmup
                          </>
                        )}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        onClick={async () => {
                          if (confirm(`Are you sure you want to disconnect sending account ${acc.email}?`)) {
                            try {
                              await disconnect.mutateAsync(acc.email);
                              import("sonner").then(({ toast }) => {
                                toast.success("Account disconnected successfully!");
                              });
                            } catch (err: any) {
                              import("sonner").then(({ toast }) => {
                                toast.error(err.message || "Failed to disconnect account.");
                              });
                            }
                          }
                        }}
                        disabled={disconnect.isPending}
                        title="Disconnect account"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-1 text-[11px] pt-1.5 border-t border-border/55 text-center">
                    <div>
                      <div className="text-muted-foreground text-[9px] uppercase font-semibold">Health</div>
                      <div className={`font-semibold flex items-center justify-center gap-0.5 mt-0.5 ${health >= 90 ? "text-emerald-500" : health >= 70 ? "text-amber-500" : "text-destructive"}`}>
                        <Heart className="h-3 w-3 fill-current text-rose-500" />
                        {health}%
                      </div>
                    </div>
                    <div className="border-l border-border/50">
                      <div className="text-muted-foreground text-[9px] uppercase font-semibold">Sent</div>
                      <div className="font-mono mt-0.5">{acc.sent_count}</div>
                    </div>
                    <div className="border-l border-border/50">
                      <div className="text-muted-foreground text-[9px] uppercase font-semibold">Recv</div>
                      <div className="font-mono mt-0.5">{acc.received_count}</div>
                    </div>
                    <div className="border-l border-border/50">
                      <div className="text-muted-foreground text-[9px] uppercase font-semibold">Inbox</div>
                      <div className="font-mono mt-0.5">{acc.landed_inbox}</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Connect Account Modal */}
      <Dialog open={showConnectModal} onOpenChange={setShowConnectModal}>
        <DialogContent className="sm:max-w-md bg-card border-card-border text-foreground">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm font-semibold">
              <Mail className="h-4 w-4 text-primary" />
              Connect Sending Account
            </DialogTitle>
          </DialogHeader>
          
          <form onSubmit={handleConnect} className="space-y-3.5 py-1">
            {connectError && (
              <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                {connectError}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">First Name</Label>
                <Input
                  required
                  placeholder="John"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="h-8 text-xs bg-background"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Last Name</Label>
                <Input
                  required
                  placeholder="Doe"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="h-8 text-xs bg-background"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Email Address</Label>
              <Input
                required
                type="email"
                placeholder="john.doe@yourcompany.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-8 text-xs bg-background"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Email Provider</Label>
              <Select
                value={String(providerCode)}
                onValueChange={(v) => {
                  const val = Number(v);
                  setProviderCode(val);
                  if (val === 2) {
                    setImapHost("imap.gmail.com");
                    setImapPort(993);
                    setSmtpHost("smtp.gmail.com");
                    setSmtpPort(465);
                  } else if (val === 3) {
                    setImapHost("outlook.office365.com");
                    setImapPort(993);
                    setSmtpHost("smtp.office365.com");
                    setSmtpPort(587);
                  } else {
                    setImapHost("");
                    setImapPort(993);
                    setSmtpHost("");
                    setSmtpPort(465);
                  }
                }}
              >
                <SelectTrigger className="h-8 text-xs bg-background">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="2">Google Workspace / Gmail (App Password)</SelectItem>
                  <SelectItem value="3">Microsoft Outlook (App Password)</SelectItem>
                  <SelectItem value="1">Custom IMAP/SMTP</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">
                {providerCode === 2 || providerCode === 3 ? "App Password" : "SMTP/IMAP Password"}
              </Label>
              <Input
                required
                type="password"
                placeholder="••••••••••••••••"
                value={appPassword}
                onChange={(e) => setAppPassword(e.target.value)}
                className="h-8 text-xs bg-background"
              />
              {(providerCode === 2 || providerCode === 3) && (
                <p className="text-[10px] text-muted-foreground leading-normal">
                  Generate a 16-character App Password in your account security settings. Do not use your primary sign-in password.
                </p>
              )}
            </div>

            {providerCode === 1 && (
              <div className="rounded border border-border bg-background/25 p-3 space-y-3">
                <div className="text-[11px] font-semibold text-muted-foreground border-b border-border/60 pb-1">
                  IMAP/SMTP Server Settings
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <Label className="text-[10px]">IMAP Host</Label>
                    <Input
                      required
                      placeholder="imap.domain.com"
                      value={imapHost}
                      onChange={(e) => setImapHost(e.target.value)}
                      className="h-7 text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px]">IMAP Port</Label>
                    <Input
                      required
                      type="number"
                      value={imapPort}
                      onChange={(e) => setImapPort(Number(e.target.value))}
                      className="h-7 text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px]">SMTP Host</Label>
                    <Input
                      required
                      placeholder="smtp.domain.com"
                      value={smtpHost}
                      onChange={(e) => setSmtpHost(e.target.value)}
                      className="h-7 text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px]">SMTP Port</Label>
                    <Input
                      required
                      type="number"
                      value={smtpPort}
                      onChange={(e) => setSmtpPort(Number(e.target.value))}
                      className="h-7 text-xs"
                    />
                  </div>
                </div>
              </div>
            )}

            <DialogFooter className="pt-2">
              <Button type="button" variant="ghost" className="h-8 text-xs" onClick={() => setShowConnectModal(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={connect.isPending} className="h-8 text-xs">
                {connect.isPending ? (
                  <>
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  "Connect Account"
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function CampaignsListCard({
  sequence,
  campaigns: providedCampaigns,
  contactId,
  onPause,
  onResume,
  isPausing,
  isResuming,
  isFetching,
  onRefresh
}: {
  sequence?: any;
  campaigns?: any[];
  contactId?: string;
  onPause: (campId: string) => void;
  onResume: (campId: string) => void;
  isPausing: boolean;
  isResuming: boolean;
  isFetching: boolean;
  onRefresh: () => void;
}) {
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null);
  const [modalCampaignId, setModalCampaignId] = useState<string | null>(null);
  const [selectedLeadEmail, setSelectedLeadEmail] = useState<string | null>(null);
  const [leadSearch, setLeadSearch] = useState("");

  const campaigns = providedCampaigns ?? sequence?.campaigns ?? [];

  // Automatically select the first campaign if none is selected
  useEffect(() => {
    if (campaigns.length > 0 && !selectedCampaignId) {
      setSelectedCampaignId(campaigns[0].instantly_campaign_id);
    }
  }, [campaigns, selectedCampaignId]);

  const selectedCampaign = campaigns.find(
    (c: any) => c.instantly_campaign_id === selectedCampaignId
  );

  const modalCampaign = campaigns.find(
    (c: any) => c.instantly_campaign_id === modalCampaignId
  );

  const { data: leads, isLoading: isLoadingLeads } = useCampaignLeads(modalCampaignId ?? undefined);
  const { data: leadReplies, isFetching: isLeadRepliesFetching, isLoading: isLoadingReplies, refetch: refetchLeadReplies } = useLeadReplies(selectedLeadEmail ?? undefined);

  const getLeadStatusLabel = (status: number | string | undefined | null) => {
    if (status === undefined || status === null) return "Uploaded";
    
    const normalized = String(status).toLowerCase().trim();
    if (normalized === "uploaded") return "Uploaded";
    if (normalized === "contacted") return "Contacted";
    if (normalized === "bounced") return "Bounced";
    if (normalized === "reply received" || normalized === "replied" || normalized === "reply_received") return "Reply Received";
    if (normalized === "completed") return "Completed";
    if (normalized === "unsubscribed") return "Unsubscribed";
    if (normalized === "interested") return "Interested";
    if (normalized === "meeting booked" || normalized === "meeting_booked") return "Meeting Booked";

    const s = Number(status);
    if (!isNaN(s)) {
      switch (s) {
        case 0: return "Uploaded";
        case 1: return "Contacted";
        case 2: return "Bounced";
        case 3: return "Reply Received";
        case 4: return "Completed";
        case 5: return "Unsubscribed";
        case 6: return "Interested";
        case 7: return "Meeting Booked";
      }
    }
    
    return String(status).charAt(0).toUpperCase() + String(status).slice(1);
  };

  const getLeadStatusStyle = (status: number | string | undefined | null) => {
    if (status === undefined || status === null) return "bg-muted text-muted-foreground";
    
    const normalized = String(status).toLowerCase().trim();
    if (normalized === "uploaded") return "bg-muted text-muted-foreground";
    if (normalized === "contacted") return "bg-blue-500/10 text-blue-400 border border-blue-500/20";
    if (normalized === "bounced") return "bg-destructive/10 text-destructive border border-destructive/20";
    if (normalized === "reply received" || normalized === "replied" || normalized === "reply_received") return "bg-purple-500/10 text-purple-400 border border-purple-500/20";
    if (normalized === "completed") return "bg-gray-500/10 text-gray-400 border border-gray-500/20";
    if (normalized === "unsubscribed") return "bg-amber-500/10 text-amber-500 border border-amber-500/20";
    if (normalized === "interested") return "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-semibold";
    if (normalized === "meeting booked" || normalized === "meeting_booked") return "bg-emerald-600 text-white font-bold";

    const s = Number(status);
    if (!isNaN(s)) {
      switch (s) {
        case 0: return "bg-muted text-muted-foreground";
        case 1: return "bg-blue-500/10 text-blue-400 border border-blue-500/20";
        case 2: return "bg-destructive/10 text-destructive border border-destructive/20";
        case 3: return "bg-purple-500/10 text-purple-400 border border-purple-500/20";
        case 4: return "bg-gray-500/10 text-gray-400 border border-gray-500/20";
        case 5: return "bg-amber-500/10 text-amber-500 border border-amber-500/20";
        case 6: return "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-semibold";
        case 7: return "bg-emerald-600 text-white font-bold";
      }
    }
    
    return "bg-muted text-muted-foreground";
  };

  const filteredLeads = (leads ?? []).filter(lead => {
    const term = leadSearch.toLowerCase().trim();
    if (!term) return true;
    const name = `${lead.first_name || ""} ${lead.last_name || ""}`.toLowerCase();
    const email = (lead.email || "").toLowerCase();
    const company = (lead.company_name || "").toLowerCase();
    return name.includes(term) || email.includes(term) || company.includes(term);
  });

  const modalStats = modalCampaign?.analytics;

  return (
    <Card className="border-card-border bg-card p-4 flex flex-col h-[550px]">
      <div className="mb-3 flex items-center justify-between border-b border-border/60 pb-2">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-primary animate-pulse" />
          <span className="text-sm font-semibold">Campaigns Board</span>
          <button 
            onClick={() => {
              onRefresh();
            }} 
            className="text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded"
            title="Refresh campaigns"
            disabled={isFetching}
          >
            <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
          </button>
        </div>
        {campaigns.length > 0 && (
          <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-medium text-primary">
            {campaigns.length} campaign(s)
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {campaigns.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-6 text-xs text-muted-foreground gap-2">
            <Activity className="h-8 w-8 text-muted-foreground/40" />
            <span>No campaigns created yet. Click Launch to create one.</span>
          </div>
        ) : (
          <div className="space-y-3">
            {campaigns.map((camp: any) => {
              const stats = camp.analytics || {
                sent: 0,
                reply_rate: 0,
                email_list: []
              };
              const isPaused = camp.status === "paused";
              const isComplete = camp.status === "complete";

              return (
                <div
                  key={camp.instantly_campaign_id}
                  onClick={() => {
                    setModalCampaignId(camp.instantly_campaign_id);
                    setSelectedCampaignId(camp.instantly_campaign_id);
                    setSelectedLeadEmail(null);
                    setLeadSearch("");
                  }}
                  className="cursor-pointer rounded-lg border border-border bg-background/30 hover:bg-background/55 hover:border-primary/50 text-foreground p-3 space-y-2.5 transition-all animate-fade-in"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-semibold text-xs truncate">
                        {camp.name || `Campaign: ${camp.instantly_campaign_id.slice(0, 8)}`}
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {camp.synced_at ? `Synced: ${fmtDate(camp.synced_at)}` : "Not synced"}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                      {!isComplete && (
                        isPaused ? (
                          <Button
                            size="sm"
                            className="h-6 px-2 text-[10px] bg-primary text-primary-foreground hover:bg-primary/95"
                            onClick={() => onResume(camp.instantly_campaign_id)}
                            disabled={isResuming}
                          >
                            <Play className="mr-1 h-3 w-3" />
                            Start
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-6 px-2 text-[10px] border-amber-500/40 text-amber-500 hover:bg-amber-500/10"
                            onClick={() => onPause(camp.instantly_campaign_id)}
                            disabled={isPausing}
                          >
                            <Pause className="mr-1 h-3 w-3" />
                            Stop
                          </Button>
                        )
                      )}
                      <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${
                        isPaused 
                          ? "bg-amber-500/15 text-amber-500" 
                          : isComplete 
                            ? "bg-emerald-500/15 text-emerald-500" 
                            : "bg-primary/15 text-primary"
                      }`}>
                        {camp.status}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-2 pt-2 border-t border-border/50">
                    <div className="grid grid-cols-2 gap-1 text-[11px] text-center">
                      <div>
                        <div className="text-muted-foreground text-[9px] uppercase font-semibold">Sent</div>
                        <div className="font-mono mt-0.5 font-bold">{stats.sent}</div>
                      </div>
                      <div className="border-l border-border/50">
                        <div className="text-muted-foreground text-[9px] uppercase font-semibold">Reply %</div>
                        <div className="font-mono mt-0.5 font-bold text-emerald-500">{stats.reply_rate}%</div>
                      </div>
                    </div>

                    {stats.email_list && stats.email_list.length > 0 && (
                      <div className="text-[10px] text-left text-muted-foreground border-t border-border/40 pt-1.5 px-0.5 truncate">
                        <span className="font-semibold text-foreground/80">Sender: </span>
                        <span className="font-mono">{stats.email_list.join(", ")}</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 70%+ Screen Width Modal/Popup Dialog */}
      <Dialog open={!!modalCampaignId} onOpenChange={(open) => {
        if (!open) {
          setModalCampaignId(null);
          setSelectedLeadEmail(null);
        }
      }}>
        <DialogContent className="max-w-[80vw] w-[80vw] h-[80vh] max-h-[80vh] flex flex-col bg-card border-card-border text-foreground p-6">
          <DialogHeader className="border-b border-border/50 pb-3">
            <DialogTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-5 w-5 text-primary" />
                <span className="text-base font-semibold">
                  Campaign: {modalCampaignId?.slice(0, 8)}
                </span>
                {modalCampaign && (
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    modalCampaign.status === "paused"
                      ? "bg-amber-500/15 text-amber-500"
                      : modalCampaign.status === "complete"
                        ? "bg-emerald-500/15 text-emerald-500"
                        : "bg-primary/15 text-primary"
                  }`}>
                    {modalCampaign.status}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-xs font-normal text-muted-foreground mr-6">
                {modalStats && (
                  <div className="flex items-center gap-3 bg-muted/30 px-3 py-1.5 rounded-md border border-border/45">
                    <div>
                      <span className="font-semibold text-foreground">{modalStats.sent}</span> Sent
                    </div>
                    <div className="h-3 w-px bg-border/50" />
                    <div>
                      <span className="font-semibold text-emerald-500">{modalStats.reply_rate}%</span> Reply Rate
                    </div>
                  </div>
                )}
                {modalStats?.email_list && modalStats.email_list.length > 0 && (
                  <div className="max-w-[200px] truncate">
                    <span className="font-semibold text-foreground/80">Sender: </span>
                    <span className="font-mono">{modalStats.email_list.join(", ")}</span>
                  </div>
                )}
              </div>
            </DialogTitle>
          </DialogHeader>

          {/* Dialog Main Content - Split Screen */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 flex-1 min-h-0 overflow-hidden pt-4">
            {/* Left side: Leads list */}
            <div className="md:col-span-5 flex flex-col h-full overflow-hidden border-r border-border/50 pr-4">
              <div className="mb-3">
                <Label className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">
                  Leads in Campaign
                </Label>
                <div className="relative mt-1">
                  <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                  <Input
                    placeholder="Search leads by name, email..."
                    value={leadSearch}
                    onChange={(e) => setLeadSearch(e.target.value)}
                    className="h-8 text-xs pl-8 bg-background"
                  />
                </div>
              </div>

              {isLoadingLeads ? (
                <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin text-primary" />
                  Loading leads...
                </div>
              ) : filteredLeads.length === 0 ? (
                <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground italic">
                  No leads found.
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin">
                  {filteredLeads.map((lead) => {
                    const isLeadSelected = selectedLeadEmail === lead.email;
                    const statusLabel = getLeadStatusLabel(lead.status);
                    const statusStyle = getLeadStatusStyle(lead.status);

                    return (
                      <div
                        key={lead.email}
                        onClick={() => setSelectedLeadEmail(lead.email)}
                        className={`cursor-pointer rounded-lg border p-3 flex items-center justify-between transition-all ${
                          isLeadSelected
                            ? "border-primary bg-primary/5"
                            : "border-border bg-background/20 hover:bg-background/45"
                        }`}
                      >
                        <div className="min-w-0 flex-1 pr-3">
                          <div className="font-semibold text-xs text-foreground truncate">
                            {lead.first_name || lead.last_name
                              ? `${lead.first_name || ""} ${lead.last_name || ""}`.trim()
                              : "Unknown Name"}
                          </div>
                          <div className="text-[10px] text-muted-foreground font-mono truncate">
                            {lead.email}
                          </div>
                          {lead.company_name && (
                            <div className="text-[10px] text-muted-foreground truncate mt-0.5">
                              {lead.company_name}
                            </div>
                          )}
                        </div>
                        <span className={`rounded-full px-2 py-0.5 text-[9px] font-medium shrink-0 ${statusStyle}`}>
                          {statusLabel}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Right side: Lead Conversation thread */}
            <div className="md:col-span-7 flex flex-col h-full overflow-hidden">
              {selectedLeadEmail ? (
                <div className="flex flex-col h-full overflow-hidden">
                  <div className="mb-3 flex items-center justify-between border-b border-border/40 pb-2">
                    <div className="min-w-0">
                      <div className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">
                        Conversation Thread
                      </div>
                      <div className="text-xs font-semibold text-foreground truncate mt-0.5 font-mono">
                        {selectedLeadEmail}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => refetchLeadReplies()}
                      className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                      disabled={isLeadRepliesFetching}
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${isLeadRepliesFetching ? "animate-spin" : ""}`} />
                    </Button>
                  </div>

                  {isLoadingReplies ? (
                    <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground">
                      <Loader2 className="mr-2 h-4 w-4 animate-spin text-primary" />
                      Loading replies...
                    </div>
                  ) : !leadReplies || leadReplies.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground italic border border-dashed border-border rounded-lg bg-background/10">
                      No emails sent or replies received for this lead yet.
                    </div>
                  ) : (
                    <div className="flex-1 overflow-y-auto space-y-3 pr-1 scrollbar-thin">
                      {[...leadReplies]
                        .sort((a, b) => new Date(a.timestamp_created || 0).getTime() - new Date(b.timestamp_created || 0).getTime())
                        .map((reply) => {
                        const isOutgoing = reply.ue_type === 1;
                        return (
                          <div
                            key={reply.id}
                            className={`p-3 rounded-lg text-xs leading-normal border ${
                              isOutgoing
                                ? "bg-muted/30 border-border/40 ml-8 text-foreground/90"
                                : "bg-primary/5 border-primary/20 mr-8 text-foreground font-medium"
                            }`}
                          >
                            <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1.5">
                              <span className="font-semibold truncate">
                                {isOutgoing
                                  ? `To: ${reply.to_address_email || "Lead"}`
                                  : `From: ${reply.from_address_name || reply.from_address_email || "Lead"}`}
                              </span>
                              <span>{fmtDate(reply.timestamp_created)}</span>
                            </div>
                            {reply.subject && (
                              <div className="font-semibold text-xs mb-1 truncate text-foreground/80">
                                Subject: {reply.subject}
                              </div>
                            )}
                            <div className="whitespace-pre-wrap break-words text-foreground/85 font-sans leading-relaxed">
                              {reply.body}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-xs text-muted-foreground border border-dashed border-border rounded-lg bg-background/10 gap-2">
                  <Mail className="h-8 w-8 text-muted-foreground/30" />
                  <span>Select a lead from the list to view their email thread history.</span>
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

