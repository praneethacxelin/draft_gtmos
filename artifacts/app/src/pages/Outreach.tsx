import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageHeader } from "@/components/PageHeader";
import { TierBadge, StatusPill } from "@/components/Pills";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { useContacts } from "@/hooks/useContacts";
import {
  useSequenceByContact,
  useGenerateSequence,
  useDeliverabilityCheck,
  useLaunchSequence,
  useUpdateSequenceStep,
} from "@/hooks/useSequences";
import { Mail, Linkedin, Phone, ShieldCheck, Send, Wand2, Pencil, X, FlaskConical, Check, Megaphone, Search } from "lucide-react";
import { fmtDate } from "@/lib/format";
import { ReasoningPanel, SourceBadge } from "@/components/ReasoningPanel";
import { RetriggerBar, type RetriggerAction } from "@/components/RetriggerBar";

const SOURCE_META: Record<string, { label: string; icon: typeof FlaskConical }> = {
  experiment: { label: "From experiments", icon: FlaskConical },
  campaign: { label: "From campaigns", icon: Megaphone },
  discovery: { label: "From discovery", icon: Search },
};
const SOURCE_ORDER = ["experiment", "campaign", "discovery"] as const;

interface StepDraft {
  subject: string;
  body: string;
  channel: "email" | "linkedin" | "call";
  wait_days: number;
  send_at?: string;
}

export function Outreach() {
  const { active, activeId } = useActiveStrategy();
  const { data: contacts } = useContacts(activeId ?? undefined);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (!selected && contacts && contacts[0]) setSelected(contacts[0].id);
  }, [contacts, selected]);

  const { data: sequence } = useSequenceByContact(selected ?? undefined);
  const generate = useGenerateSequence();
  const check = useDeliverabilityCheck();
  const launch = useLaunchSequence();
  const patchStep = useUpdateSequenceStep();

  const contact = contacts?.find((c) => c.id === selected);

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
      onClick: () => selected && generate.mutate(selected),
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
      <div className="mb-4 rounded border border-border bg-card p-4 space-y-4">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 shrink-0 text-amber-400" />
          <span className="text-sm font-semibold">Launch Settings</span>
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
        <Card className="lg:col-span-4 border-card-border bg-card p-3">
          <div className="mb-2 px-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Contacts
          </div>
          <div className="space-y-3">
            {SOURCE_ORDER.map((src) => {
              const group = (contacts ?? []).filter(
                (c) => (c.source ?? "discovery") === src,
              );
              if (group.length === 0) return null;
              const meta = SOURCE_META[src];
              const Icon = meta.icon;
              return (
                <div key={src} className="space-y-1">
                  <div className="flex items-center gap-1.5 px-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                    <Icon className="h-3 w-3" />
                    {meta.label}
                    <span className="text-muted-foreground/70">({group.length})</span>
                  </div>
                  {group.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => {
                        setSelected(c.id);
                        setEditingStepId(null);
                        setStepDirty(false);
                      }}
                      className={`flex w-full items-center justify-between rounded px-3 py-2 text-left text-sm hover-elevate ${
                        selected === c.id ? "bg-sidebar-accent" : ""
                      }`}
                      data-testid={`contact-row-${c.id}`}
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">
                          {c.full_name}
                        </div>
                        <div className="truncate text-[11px] text-muted-foreground">
                          {c.title} · {c.company_name}
                        </div>
                      </div>
                      <TierBadge tier={c.tier} />
                    </button>
                  ))}
                </div>
              );
            })}
            {(!contacts || contacts.length === 0) && (
              <div className="px-3 py-6 text-center text-xs text-muted-foreground">
                No contacts yet. Run lead discovery first.
              </div>
            )}
          </div>
        </Card>

        <div className="lg:col-span-8 space-y-4">
          <Card className="border-card-border bg-card p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-base font-semibold">
                  {contact?.full_name ?? "Select a contact"}
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
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!selected || generate.isPending}
                  onClick={() => selected && generate.mutate(selected)}
                  data-testid="button-generate-sequence"
                >
                  <Wand2 className="mr-2 h-4 w-4" />
                  {generate.isPending ? "Generating…" : "Generate"}
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
                          {s.subject ||
                            (s.channel === "call"
                              ? "Call talking points"
                              : "(no subject)")}
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
                      {s.body || "—"}
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
      </div>
    </>
  );
}
