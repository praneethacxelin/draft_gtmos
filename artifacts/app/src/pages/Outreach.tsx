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
import { useContacts, useVerifyContactEmail } from "@/hooks/useContacts";
import { useToast } from "@/hooks/use-toast";
import {
  useSequenceByContact,
  useGenerateSequence,
  useDeliverabilityCheck,
  useLaunchSequence,
  useUpdateSequenceStep,
} from "@/hooks/useSequences";
import { Mail, Linkedin, Phone, ShieldCheck, Send, Wand2, Pencil, X, FlaskConical, Check, Megaphone, Search, BadgeCheck, CheckCircle2, XCircle, HelpCircle, Loader2 } from "lucide-react";
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
  const verifyEmail = useVerifyContactEmail();
  const { toast } = useToast();

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

  // Test-mode email — persisted in localStorage so it survives page refreshes
  const [testEmail, setTestEmail] = useState<string>(
    () => localStorage.getItem("gtm_test_email") ?? "",
  );
  const [testEmailDraft, setTestEmailDraft] = useState("");
  const [editingTestEmail, setEditingTestEmail] = useState(false);

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

  if (!activeId) {
    return (
      <div className="rounded border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        Select an active strategy to plan outreach.
      </div>
    );
  }

  const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const presetTzs = ["UTC", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Europe/London", "Asia/Kolkata"];
  const [schedule, setSchedule] = useState({
    timezone: browserTz,
    time_from: "09:00",
    time_to: "17:00",
    days: { "0": false, "1": true, "2": true, "3": true, "4": true, "5": true, "6": false }
  });

  const toggleDay = (d: string) => {
    setSchedule(s => ({ ...s, days: { ...s.days, [d]: !s.days[d as keyof typeof s.days] } }));
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
            <Select value={schedule.timezone} onValueChange={(v) => setSchedule(s => ({ ...s, timezone: v }))}>
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
                onChange={(e) => setSchedule(s => ({ ...s, time_from: e.target.value }))}
                className="h-8 text-xs w-[100px]" 
              />
              <span className="text-muted-foreground text-xs">to</span>
              <Input 
                type="time" 
                value={schedule.time_to} 
                onChange={(e) => setSchedule(s => ({ ...s, time_to: e.target.value }))}
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
                {contact && (
                  <div className="mt-1 flex items-center gap-1.5 text-xs">
                    <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                    {contact.email &&
                    contact.email !== "Not found" &&
                    contact.email !== "(not revealed)" ? (
                      <span className="font-mono text-foreground/80">{contact.email}</span>
                    ) : (
                      <span className="text-muted-foreground/60">
                        No email yet — reveal it on the Prospects page first
                      </span>
                    )}
                    {contact.email_verified === "valid" && (
                      <span className="ml-0.5 inline-flex items-center gap-1 rounded bg-primary/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-primary">
                        <CheckCircle2 className="h-3 w-3" /> Valid
                      </span>
                    )}
                    {contact.email_verified === "invalid" && (
                      <span className="ml-0.5 inline-flex items-center gap-1 rounded bg-destructive/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-destructive">
                        <XCircle className="h-3 w-3" /> Invalid
                      </span>
                    )}
                    {contact.email_verified === "catch_all" && (
                      <span className="ml-0.5 inline-flex items-center gap-1 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-amber-500">
                        <HelpCircle className="h-3 w-3" /> Catch-all
                      </span>
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
                      <span
                        className="rounded bg-purple-500/15 px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-purple-400"
                        title="Test send — not pushed to Instantly. Happens when you use 'Simulate window' or when no Instantly key was set at launch time."
                      >
                        Simulated (test send)
                      </span>
                    )}
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={
                    !contact ||
                    !contact.email ||
                    contact.email === "Not found" ||
                    contact.email === "(not revealed)" ||
                    verifyEmail.isPending
                  }
                  onClick={() =>
                    selected &&
                    verifyEmail.mutate(
                      { id: selected, provider: "instantly" },
                      {
                        onSuccess: (data) => {
                          const s = data.email_verified;
                          toast({
                            title:
                              s === "valid"
                                ? "Email verified — safe to send"
                                : s === "invalid"
                                  ? "Email is invalid"
                                  : s === "catch_all"
                                    ? "Catch-all domain — send with caution"
                                    : "Verification pending",
                            description:
                              s === "valid"
                                ? `${data.email} passed Instantly verification.`
                                : s === "invalid"
                                  ? `${data.email} would likely bounce. Re-reveal or skip this contact.`
                                  : `Instantly returned "${s}" for ${data.email}.`,
                            variant: s === "invalid" ? "destructive" : undefined,
                          });
                        },
                        onError: (err: any) =>
                          toast({
                            title: "Verification failed",
                            description:
                              err.message ||
                              "Configure Instantly (or Hunter) in Settings → Integrations.",
                            variant: "destructive",
                          }),
                      },
                    )
                  }
                  data-testid="button-verify-email"
                  title="Verify the email with Instantly before generating the sequence"
                >
                  {verifyEmail.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <BadgeCheck className="mr-2 h-4 w-4" />
                  )}
                  {verifyEmail.isPending ? "Verifying…" : "Verify email"}
                </Button>
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
                <Button
                  size="sm"
                  disabled={!sequence || launch.isPending}
                  onClick={() =>
                    sequence &&
                    launch.mutate({
                      sequenceId: sequence.id,
                      testEmail: testEmail || undefined,
                      schedule: schedule,
                    })
                  }
                  data-testid="button-launch"
                  title={testEmail ? `Will send to ${testEmail} (test mode)` : "Launch via Instantly"}
                >
                  <Send className="mr-2 h-4 w-4" />
                  {launch.isPending
                    ? "Launching…"
                    : testEmail
                      ? "Launch → test inbox"
                      : "Launch"}
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
                      <div className="grid grid-cols-3 gap-3">
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
                        <div className="col-span-1 flex items-end">
                          <div className="rounded-md bg-muted/50 border border-border px-3 py-1.5 text-[10px] text-muted-foreground leading-snug">
                            ⏰ Sending window is set at campaign level via Instantly.ai (e.g. 9am–5pm weekdays). Individual step timing uses the delay above.
                          </div>
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
