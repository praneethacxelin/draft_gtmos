import { useState, useEffect, useMemo } from "react";
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
import { PageHeader } from "@/components/PageHeader";
import { TierBadge, StatusPill } from "@/components/Pills";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { useContacts, useUpdateContact } from "@/hooks/useContacts";
import { useSenderStatus } from "@/hooks/useSettings";
import {
  useSequenceByContact,
  useGenerateSequence,
  useDeliverabilityCheck,
  useLaunchSequence,
  useUpdateSequenceStep,
} from "@/hooks/useSequences";
import {
  Mail,
  Linkedin,
  Phone,
  ShieldCheck,
  Send,
  Wand2,
  Pencil,
  X,
  FlaskConical,
  Check,
  Users,
  Eye,
  Code2,
  ClipboardCheck,
} from "lucide-react";
import { fmtDate } from "@/lib/format";
import { ReasoningPanel, SourceBadge } from "@/components/ReasoningPanel";
import { RetriggerBar, type RetriggerAction } from "@/components/RetriggerBar";
import { useToast } from "@/hooks/use-toast";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface StepDraft {
  subject: string;
  body: string;
  channel: "email" | "linkedin" | "call";
  wait_days: number;
  send_at?: string;
}

interface ReviewDraft {
  full_name: string;
  email: string;
  title: string;
  company_name: string;
  industry: string;
  department: string;
  persona_type: string;
  seniority: string;
  pain_point: string;
  recent_signal: string;
  icebreaker: string;
}

type ViewMode = "template" | "preview";
type PanelView = "sequence" | "review";

// ---------------------------------------------------------------------------
// Dynamic variable helpers
// ---------------------------------------------------------------------------
const VAR_DEFS = [
  { key: "{{first_name}}",    label: "First Name" },
  { key: "{{last_name}}",     label: "Last Name" },
  { key: "{{company}}",       label: "Company" },
  { key: "{{title}}",         label: "Title" },
  { key: "{{industry}}",      label: "Industry" },
  { key: "{{department}}",    label: "Department" },
  { key: "{{location}}",      label: "Location" },
  { key: "{{pain_point}}",    label: "Pain Point" },
  { key: "{{recent_signal}}", label: "Recent Signal" },
  { key: "{{icebreaker}}",    label: "Icebreaker" },
];

function resolveVars(contact: any, account: any): Record<string, string> {
  const nameParts = (contact?.full_name || "").split(" ");
  return {
    "{{first_name}}":    nameParts[0] || "",
    "{{last_name}}":     nameParts.slice(1).join(" ") || "",
    "{{company}}":       account?.company_name || "",
    "{{title}}":         contact?.title || "",
    "{{industry}}":      account?.industry || "",
    "{{department}}":    contact?.department || "",
    "{{location}}":      contact?.location || "",
    "{{pain_point}}":    contact?.pain_point || "",
    "{{recent_signal}}": contact?.recent_signal || "",
    "{{icebreaker}}":    contact?.icebreaker || "",
  };
}

function renderVariables(text: string, contact: any, account: any): string {
  if (!text) return text;
  const vars = resolveVars(contact, account);
  let out = text;
  for (const [k, v] of Object.entries(vars)) {
    out = out.replace(new RegExp(k.replace(/[{}]/g, "\\$&"), "g"), v || k);
  }
  return out;
}

// Highlight raw variable tokens in template view
function TemplateText({ text }: { text: string }) {
  const parts = text.split(/({{[^}]+}})/g);
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

// Placeholder cards shown when no sequence has been generated yet
const PLACEHOLDER_STEPS = [
  { step: 1, channel: "email",    subject: "[AI-generated subject will appear here]",     body: "[Generate a sequence to preview personalized outreach]",     wait: 0  },
  { step: 2, channel: "email",    subject: "[Follow-up subject]",                         body: "[Follow-up content will appear here after generation]",       wait: 3  },
  { step: 3, channel: "linkedin", subject: "[LinkedIn message]",                           body: "[LinkedIn outreach content will appear after generation]",    wait: 5  },
  { step: 4, channel: "call",     subject: "[Call talking points]",                        body: "[Talking-point outline will appear after generation]",        wait: 7  },
];

function channelIcon(channel: string, cls = "h-4 w-4") {
  if (channel === "email")    return <Mail className={cls} />;
  if (channel === "linkedin") return <Linkedin className={cls} />;
  return <Phone className={cls} />;
}

function channelBg(channel: string) {
  if (channel === "email")    return "bg-primary/15 text-primary";
  if (channel === "linkedin") return "bg-blue-500/15 text-blue-400";
  return "bg-amber-500/15 text-amber-400";
}

function ReviewField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}

function ReviewInput({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <ReviewField label={label}>
      <Input value={value} onChange={(event) => onChange(event.target.value)} className="h-8 text-sm" type={type} />
    </ReviewField>
  );
}

function ReviewTextarea({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <ReviewField label={label}>
      <Textarea value={value} onChange={(event) => onChange(event.target.value)} rows={3} className="text-sm" />
    </ReviewField>
  );
}

function ReviewSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <ReviewField label={label}>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="h-8 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </ReviewField>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function Outreach() {
  const { active, activeId } = useActiveStrategy();
  const { data: contacts } = useContacts(activeId ?? undefined);

  const [selectedIds, setSelectedIds]       = useState<Set<string>>(new Set());
  const [activeContactId, setActiveContactId] = useState<string | null>(null);
  const [viewMode, setViewMode]             = useState<ViewMode>("preview");
  const [panelView, setPanelView]           = useState<PanelView>("sequence");

  const { toast } = useToast();

  useEffect(() => {
    if (!activeContactId && contacts && contacts.length > 0) {
      setActiveContactId(contacts[0].id);
      setSelectedIds(new Set([contacts[0].id]));
    }
  }, [contacts, activeContactId]);

  const { data: sequence } = useSequenceByContact(activeContactId ?? undefined);
  const generate   = useGenerateSequence();
  const check      = useDeliverabilityCheck();
  const launch     = useLaunchSequence();
  const patchStep  = useUpdateSequenceStep();

  const activeContact = contacts?.find((c) => c.id === activeContactId);
  const account       = { company_name: activeContact?.company_name, industry: activeContact?.industry };
  const varValues     = resolveVars(activeContact, account);
  const sequenceChannelSummary = useMemo(() => {
    const channels = sequence?.channel_plan?.map((step) => step.channel)
      ?? sequence?.steps.map((step) => step.channel)
      ?? [];
    const uniqueChannels = Array.from(new Set(channels.filter(Boolean)));
    if (uniqueChannels.length === 0) return "—";
    return uniqueChannels
      .map((channel) => channel.charAt(0).toUpperCase() + channel.slice(1))
      .join(" + ");
  }, [sequence]);

  // Smart persona grouping
  const groupedContacts = useMemo(() => {
    if (!contacts) return [];
    const groups: Record<string, typeof contacts> = {};
    for (const c of contacts) {
      const key = [c.department, c.seniority, c.persona_type].filter(Boolean).join(" · ") || "Ungrouped";
      if (!groups[key]) groups[key] = [];
      groups[key].push(c);
    }
    return Object.entries(groups).map(([name, items], i) => ({
      name: name !== "Ungrouped" ? `Group ${String.fromCharCode(65 + i)}: ${name}` : name,
      items,
    }));
  }, [contacts]);

  // Generation options
  const [goal, setGoal]           = useState("Intro Call");
  const [tone, setTone]           = useState("Professional");
  const [seqLength, setSeqLength] = useState(4);

  // Step editing
  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [editDraft, setEditDraft]         = useState<StepDraft>({
    subject: "", body: "", channel: "email", wait_days: 1,
  });
  const [stepDirty, setStepDirty] = useState(false);

  // Contact editing state
  const [editingContactId, setEditingContactId] = useState<string | null>(null);
  const [contactEditDraft, setContactEditDraft] = useState({ full_name: "", email: "" });
  const updateContact = useUpdateContact();
  const [reviewDraft, setReviewDraft] = useState<ReviewDraft>({
    full_name: "",
    email: "",
    title: "",
    company_name: "",
    industry: "",
    department: "",
    persona_type: "",
    seniority: "",
    pain_point: "",
    recent_signal: "",
    icebreaker: "",
  });

  // Instantly sender status
  const { data: senderStatus } = useSenderStatus();

  // Bulk generation state
  const [isGeneratingBulk, setIsGeneratingBulk] = useState(false);
  const [localFallbackError, setLocalFallbackError] = useState(false);

  // Schedule
  const browserTz  = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const presetTzs  = ["UTC", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Europe/London", "Asia/Kolkata"];
  const [schedule, setSchedule] = useState({
    timezone: browserTz,
    time_from: "09:00",
    time_to: "17:00",
    days: { "0": false, "1": true, "2": true, "3": true, "4": true, "5": true, "6": false },
  });

  function startEditStep(stepId: string) {
    const step = sequence?.steps.find((s) => s.id === stepId);
    if (!step) return;
    let send_at_local: string | undefined;
    if (step.send_at) {
      const dt = new Date(step.send_at);
      if (!isNaN(dt.getTime()))
        send_at_local = new Date(dt.getTime() - dt.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    }
    setEditDraft({ subject: step.subject ?? "", body: step.body ?? "", channel: step.channel as any, wait_days: step.wait_days, send_at: send_at_local });
    setEditingStepId(stepId);
  }

  async function saveStep() {
    if (!editingStepId) return;
    try {
      const data = { ...editDraft };
      if (data.send_at) data.send_at = new Date(data.send_at).toISOString();
      await patchStep.mutateAsync({ id: editingStepId, data });
      setEditingStepId(null);
      setStepDirty(true);
    } catch (err) { console.error("Failed to save step:", err); }
  }

  async function handleGenerate() {
    if (selectedIds.size === 0) return;
    setIsGeneratingBulk(true);
    setLocalFallbackError(false);
    try {
      for (const id of Array.from(selectedIds))
        await generate.mutateAsync({ contactId: id, options: { goal, tone, length: seqLength } });
      toast({ title: "Sequence Generated", description: `Drafted sequences for ${selectedIds.size} contacts.` });
    } catch (err) {
      console.error(err);
      setLocalFallbackError(true);
      toast({ title: "Generation Error", description: "Fell back to existing sequences or an error occurred.", variant: "destructive" });
    } finally { setIsGeneratingBulk(false); }
  }

  function handleSelectSimilar() {
    if (!activeContact) return;
    const { department, seniority, persona_type } = activeContact;
    const next = new Set(selectedIds);
    contacts?.forEach(c => {
      if (c.department === department && c.seniority === seniority && c.persona_type === persona_type)
        next.add(c.id);
    });
    setSelectedIds(next);
  }

  const toggleDay    = (d: string) => setSchedule(s => ({ ...s, days: { ...s.days, [d]: !s.days[d as keyof typeof s.days] } }));
  const toggleSelect = (id: string) => { const n = new Set(selectedIds); n.has(id) ? n.delete(id) : n.add(id); setSelectedIds(n); };
  const toggleSelectAll = (checked: boolean) => setSelectedIds(checked ? new Set(contacts?.map(c => c.id) || []) : new Set());

  const retriggerActions: RetriggerAction[] = [
    { label: check.isPending ? "Checking…" : "Check deliverability", icon: <ShieldCheck className="h-3 w-3" />, onClick: () => sequence && check.mutate(sequence.id), isPending: check.isPending },
    { label: isGeneratingBulk ? "Generating…" : "Regenerate sequence", icon: <Wand2 className="h-3 w-3" />, onClick: handleGenerate, isPending: isGeneratingBulk },
  ];

  const daysMap = [{ k:"1",label:"M"},{k:"2",label:"T"},{k:"3",label:"W"},{k:"4",label:"T"},{k:"5",label:"F"},{k:"6",label:"S"},{k:"0",label:"S"}];

  useEffect(() => {
    if (!activeContact) return;
    setReviewDraft({
      full_name: activeContact.full_name ?? "",
      email: activeContact.email ?? "",
      title: activeContact.title ?? "",
      company_name: activeContact.company_name ?? "",
      industry: activeContact.industry ?? "",
      department: activeContact.department ?? "",
      persona_type: activeContact.persona_type ?? "",
      seniority: activeContact.seniority ?? "",
      pain_point: activeContact.pain_point ?? "",
      recent_signal: activeContact.recent_signal ?? "",
      icebreaker: activeContact.icebreaker ?? "",
    });
  }, [activeContact]);

  // -------------------------------------------------------------------------
  // Guard: no active strategy
  // -------------------------------------------------------------------------
  if (!activeId) {
    return (
      <div className="rounded border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        Select an active strategy to plan outreach.
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // Shared step display (template vs preview body text)
  // -------------------------------------------------------------------------
  function renderBody(raw: string) {
    if (!raw) return <span className="italic text-muted-foreground">[No content generated]</span>;
    if (viewMode === "template") return <TemplateText text={raw} />;
    return <>{renderVariables(raw, activeContact, account)}</>;
  }

  function renderSubject(raw: string | undefined, channel: string) {
    if (!raw) return <span className="italic text-muted-foreground">{channel === "call" ? "Call talking points" : "[No subject generated]"}</span>;
    if (viewMode === "template") return <TemplateText text={raw} />;
    return <>{renderVariables(raw, activeContact, account)}</>;
  }

  // -------------------------------------------------------------------------
  // Pre-Launch Review panel
  // -------------------------------------------------------------------------
  function ReviewPanel() {
    if (!sequence) {
      return (
        <div className="rounded border border-dashed border-border p-8 text-center">
          <div className="text-sm text-muted-foreground mb-4">No sequence generated yet.</div>
          <Button size="sm" onClick={handleGenerate} disabled={selectedIds.size === 0 || isGeneratingBulk}>
            <Wand2 className="mr-2 h-4 w-4" />
            {isGeneratingBulk ? "Generating…" : "Generate Sequence"}
          </Button>
        </div>
      );
    }

    return (
      <div className="space-y-4">
        <Card className="border-card-border bg-card p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Approval Draft</div>
              <div className="text-sm text-muted-foreground">
                Edit contact and personalization inputs here before launch so the engineer can approve the exact payload.
              </div>
            </div>
            <Button size="sm" variant="secondary" onClick={() => setPanelView("sequence")}>
              <Pencil className="mr-2 h-4 w-4" /> Edit Sequence
            </Button>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <ReviewInput label="Full Name" value={reviewDraft.full_name} onChange={(value) => setReviewDraft((draft) => ({ ...draft, full_name: value }))} />
            <ReviewInput label="Email" value={reviewDraft.email} onChange={(value) => setReviewDraft((draft) => ({ ...draft, email: value }))} type="email" />
            <ReviewInput label="Title" value={reviewDraft.title} onChange={(value) => setReviewDraft((draft) => ({ ...draft, title: value }))} />
            <ReviewInput label="Company" value={reviewDraft.company_name} onChange={(value) => setReviewDraft((draft) => ({ ...draft, company_name: value }))} />
            <ReviewInput label="Industry" value={reviewDraft.industry} onChange={(value) => setReviewDraft((draft) => ({ ...draft, industry: value }))} />
            <ReviewInput label="Department" value={reviewDraft.department} onChange={(value) => setReviewDraft((draft) => ({ ...draft, department: value }))} />
            <ReviewInput label="Persona Type" value={reviewDraft.persona_type} onChange={(value) => setReviewDraft((draft) => ({ ...draft, persona_type: value }))} />
            <ReviewInput label="Seniority" value={reviewDraft.seniority} onChange={(value) => setReviewDraft((draft) => ({ ...draft, seniority: value }))} />
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
            <ReviewTextarea label="Pain Point" value={reviewDraft.pain_point} onChange={(value) => setReviewDraft((draft) => ({ ...draft, pain_point: value }))} />
            <ReviewTextarea label="Recent Signal" value={reviewDraft.recent_signal} onChange={(value) => setReviewDraft((draft) => ({ ...draft, recent_signal: value }))} />
            <ReviewTextarea label="Icebreaker" value={reviewDraft.icebreaker} onChange={(value) => setReviewDraft((draft) => ({ ...draft, icebreaker: value }))} />
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            <ReviewSelect
              label="Goal"
              value={goal}
              onChange={setGoal}
              options={["Intro Call", "Product Demo", "Follow Up", "Re-engagement"]}
            />
            <ReviewSelect
              label="Tone"
              value={tone}
              onChange={setTone}
              options={["Professional", "Friendly", "Technical", "Executive"]}
            />
          </div>
          <div className="mt-4 rounded border border-dashed border-border bg-background/40 p-3 text-xs text-muted-foreground">
            The review form is the approval surface. Contact fields can be saved to the contact record; the other fields stay editable here so you can validate the payload before launch.
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              size="sm"
              onClick={async () => {
                if (!activeContact) return;
                try {
                  await updateContact.mutateAsync({
                    id: activeContact.id,
                    data: {
                      full_name: reviewDraft.full_name,
                      title: reviewDraft.title || undefined,
                      email: reviewDraft.email || undefined,
                      persona_type: reviewDraft.persona_type || undefined,
                      seniority: reviewDraft.seniority || undefined,
                    },
                  });
                  toast({ title: "Contact updated", description: "Saved the editable contact fields." });
                } catch (err) {
                  toast({ title: "Save failed", description: "Failed to update the contact.", variant: "destructive" });
                }
              }}
              disabled={!activeContact || updateContact.isPending}
            >
              {updateContact.isPending ? "Saving…" : "Save contact fields"}
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setPanelView("sequence")}>
              Continue editing sequence
            </Button>
          </div>
        </Card>

        {/* Contact Information */}
        <Card className="border-card-border bg-card p-4">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">Contact Information</div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
            {[
              ["Name",       reviewDraft.full_name],
              ["Title",      reviewDraft.title],
              ["Company",    reviewDraft.company_name],
              ["Industry",   reviewDraft.industry],
              ["Department", reviewDraft.department],
            ].map(([label, value]) => (
              <div key={label} className="flex gap-2 text-xs">
                <span className="text-muted-foreground shrink-0 w-20">{label}</span>
                <span className="font-medium truncate">{value || "—"}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Personalization Inputs */}
        <Card className="border-card-border bg-card p-4">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">Personalization Inputs</div>
          <div className="space-y-1.5">
            {[
              ["Pain Point",     reviewDraft.pain_point],
              ["Recent Signal",  reviewDraft.recent_signal],
              ["Icebreaker",     reviewDraft.icebreaker],
              ["Goal",           goal],
              ["Tone",           tone],
              ["Channel",        sequenceChannelSummary],
              ["Persona",        reviewDraft.persona_type],
              ["Seniority",      reviewDraft.seniority],
            ].map(([label, value]) => (
              <div key={label} className="flex gap-2 text-xs">
                <span className="text-muted-foreground shrink-0 w-28">{label}</span>
                <span className="font-medium">{value || "—"}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Sequence Preview for review */}
        <Card className="border-card-border bg-card p-4">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">Sequence Preview</div>
          <div className="space-y-4">
            {sequence.steps.map((s) => (
              <div key={s.id} className="border-l-2 border-border pl-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <div className={`flex h-6 w-6 items-center justify-center rounded text-[10px] ${channelBg(s.channel)}`}>
                    {channelIcon(s.channel, "h-3 w-3")}
                  </div>
                  <span className="text-xs uppercase tracking-widest text-muted-foreground font-semibold">
                    Step {s.step_number} · {s.channel}
                  </span>
                  <span className="text-[11px] text-muted-foreground ml-auto">
                    Wait {s.wait_days} {s.wait_days === 1 ? "day" : "days"}
                  </span>
                </div>
                <div className="text-xs font-semibold mb-1">
                  Subject: {s.subject ? renderVariables(s.subject, activeContact, account) : "[No subject generated]"}
                </div>
                <div className="text-xs text-foreground/80 whitespace-pre-wrap leading-relaxed">
                  {s.body ? renderVariables(s.body, activeContact, account) : "[No content generated]"}
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">
                  Wait Days: {s.wait_days}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Launch Payload Verification */}
        <Card className="border-card-border bg-card p-4 border-l-4 border-l-primary">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">Launch Payload Verification</div>
          <div className="space-y-1.5 text-xs">
            <div className="flex gap-2">
              <span className="text-muted-foreground shrink-0 w-24">Recipient</span>
              <span className="font-semibold text-foreground">{activeContact?.email || "No email configured"}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-muted-foreground shrink-0 w-24">Sender</span>
              <span className="font-semibold text-foreground">{senderStatus?.email || "No sender email connected"}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-muted-foreground shrink-0 w-24">Sequence Steps</span>
              <span className="font-semibold text-foreground">{sequence?.steps?.length || 0} Steps</span>
            </div>
          </div>
        </Card>

        {/* Approval actions */}
        <div className="flex gap-3">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setPanelView("sequence")}
          >
            <Pencil className="mr-2 h-4 w-4" />
            Edit Sequence
          </Button>
          <Button
            size="sm"
            disabled={!sequence || launch.isPending}
            onClick={() =>
              sequence &&
              launch.mutate({
                sequenceId: sequence.id,
                schedule,
              })
            }
            title="Launch via Instantly"
          >
            <Send className="mr-2 h-4 w-4" />
            {launch.isPending
              ? "Launching…"
              : "Approve & Launch"}
          </Button>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
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

      {/* Campaign Settings */}
      <div className="mb-4 rounded border border-border bg-card p-4 space-y-4">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 shrink-0 text-amber-400" />
          <span className="text-sm font-semibold">Launch Settings</span>
        </div>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3 lg:grid-cols-5">
          {/* Sender Email */}
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Sender Email</Label>
            <div className="text-xs font-semibold truncate pt-1" title={senderStatus?.email || "No account connected"}>
              {senderStatus?.email || "No sender email connected"}
            </div>
            <div className="text-[10px] text-muted-foreground">
              Provider: {senderStatus?.provider || "Instantly"}
            </div>
          </div>
          {/* Connection Status */}
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Connection Status</Label>
            <div className="flex items-center gap-1.5 pt-1">
              <span className={`h-2 w-2 rounded-full ${senderStatus?.status === "Connected" ? "bg-green-500" : "bg-red-500"}`} />
              <span className="text-xs font-semibold">{senderStatus?.status || "Checking..."}</span>
            </div>
            <div className="text-[10px] text-muted-foreground">
              {senderStatus?.warmup_info || "Warmup info unavailable."}
            </div>
          </div>
          {/* Timezone */}
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Timezone</Label>
            <Select value={schedule.timezone} onValueChange={v => setSchedule(s => ({ ...s, timezone: v }))}>
              <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                {presetTzs.map(tz => <SelectItem key={tz} value={tz}>{tz}</SelectItem>)}
                {!presetTzs.includes(browserTz) && <SelectItem value={browserTz}>{browserTz} (Local)</SelectItem>}
              </SelectContent>
            </Select>
          </div>
          {/* Sending window */}
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Sending Window</Label>
            <div className="flex items-center gap-2">
              <Input type="time" value={schedule.time_from} onChange={e => setSchedule(s => ({ ...s, time_from: e.target.value }))} className="h-8 text-xs w-[100px]" />
              <span className="text-muted-foreground text-xs">to</span>
              <Input type="time" value={schedule.time_to} onChange={e => setSchedule(s => ({ ...s, time_to: e.target.value }))} className="h-8 text-xs w-[100px]" />
            </div>
          </div>
          {/* Active days */}
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Active Days</Label>
            <div className="flex items-center gap-1">
              {daysMap.map(d => (
                <button key={d.k} onClick={() => toggleDay(d.k)}
                  className={`h-8 w-8 rounded text-xs font-medium transition-colors ${schedule.days[d.k as keyof typeof schedule.days] ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"}`}>
                  {d.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">

        {/* ── Left: Contact list ── */}
        <Card className="lg:col-span-4 border-card-border bg-card p-3 flex flex-col min-h-[60vh] max-h-[80vh] overflow-hidden">
          <div className="mb-2 px-2 flex items-center justify-between">
            <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground flex items-center gap-2">
              <Checkbox
                checked={selectedIds.size > 0 && selectedIds.size === contacts?.length}
                onCheckedChange={toggleSelectAll}
                className="w-4 h-4"
              />
              <span>Contacts ({selectedIds.size} selected)</span>
            </div>
            <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" onClick={handleSelectSimilar} disabled={!activeContactId}>
              <Users className="w-3 h-3 mr-1" /> Similar
            </Button>
          </div>

          <div className="space-y-4 overflow-y-auto pr-1 flex-1 pb-4">
            {groupedContacts.map(group => (
              <div key={group.name} className="space-y-1">
                <div className="px-2 text-[11px] font-semibold text-muted-foreground sticky top-0 bg-card py-1 z-10">
                  {group.name}
                </div>
                {group.items.map(c => (
                  <div key={c.id}
                    className={`flex flex-col w-full rounded px-3 py-2 text-left text-sm hover-elevate cursor-pointer ${activeContactId === c.id ? "bg-sidebar-accent border-l-2 border-primary" : ""} ${selectedIds.has(c.id) ? "bg-muted/30" : ""}`}
                    onClick={() => { setActiveContactId(c.id); setEditingStepId(null); setStepDirty(false); }}>
                    {editingContactId === c.id ? (
                      <div className="w-full space-y-2 py-1" onClick={e => e.stopPropagation()}>
                        <div className="space-y-1">
                          <Label className="text-[10px] text-muted-foreground font-semibold uppercase">Full Name</Label>
                          <Input
                            value={contactEditDraft.full_name}
                            onChange={e => setContactEditDraft({ ...contactEditDraft, full_name: e.target.value })}
                            className="h-7 text-xs bg-background"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-[10px] text-muted-foreground font-semibold uppercase">Email Address</Label>
                          <Input
                            value={contactEditDraft.email}
                            onChange={e => setContactEditDraft({ ...contactEditDraft, email: e.target.value })}
                            className="h-7 text-xs bg-background"
                            type="email"
                          />
                        </div>
                        <div className="flex gap-2 justify-end pt-1">
                          <Button
                            size="sm"
                            className="h-6 px-2 text-[10px]"
                            variant="ghost"
                            onClick={() => setEditingContactId(null)}
                          >
                            Cancel
                          </Button>
                          <Button
                            size="sm"
                            className="h-6 px-2 text-[10px]"
                            onClick={async () => {
                              try {
                                await updateContact.mutateAsync({
                                  id: c.id,
                                  data: {
                                    full_name: contactEditDraft.full_name,
                                    email: contactEditDraft.email || undefined,
                                  }
                                });
                                setEditingContactId(null);
                                toast({
                                  title: "Contact updated",
                                  description: "Changes saved successfully.",
                                });
                              } catch (err) {
                                toast({
                                  title: "Save failed",
                                  description: "Failed to update contact.",
                                  variant: "destructive",
                                });
                              }
                            }}
                            disabled={updateContact.isPending}
                          >
                            {updateContact.isPending ? "Saving..." : "Save"}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex w-full items-center justify-between">
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          <Checkbox checked={selectedIds.has(c.id)} onCheckedChange={() => toggleSelect(c.id)} onClick={e => e.stopPropagation()} className="w-4 h-4" />
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium">{c.full_name}</div>
                            <div className="truncate text-[11px] text-muted-foreground">{c.title} · {c.company_name}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
                          <TierBadge tier={c.tier} />
                          <button
                            onClick={() => {
                              setContactEditDraft({ full_name: c.full_name, email: c.email || "" });
                              setEditingContactId(c.id);
                            }}
                            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-colors"
                            title="Edit contact"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ))}
            {(!contacts || contacts.length === 0) && (
              <div className="px-3 py-6 text-center text-xs text-muted-foreground">
                No contacts yet. Run lead discovery first.
              </div>
            )}
          </div>

          {/* Personalization Data panel — always shown when a contact is active */}
          {activeContact && (
            <div className="border-t border-border pt-3 mt-2 shrink-0">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-2 px-1">
                Personalization Data
              </div>
              <div className="space-y-1 px-1">
                {VAR_DEFS.map(({ key, label }) => {
                  const val = varValues[key];
                  return (
                    <div key={key} className="flex items-start gap-2 text-[11px]">
                      <span className="text-muted-foreground shrink-0 w-24">{label}</span>
                      {val
                        ? <span className="font-medium text-foreground truncate">{val}</span>
                        : <span className="italic text-muted-foreground/60">—</span>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Card>

        {/* ── Right: Workspace ── */}
        <div className="lg:col-span-8 space-y-4 min-h-[60vh] max-h-[80vh] overflow-y-auto pb-8">

          {/* Control card */}
          <Card className="border-card-border bg-card p-5">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              {/* Contact header */}
              <div>
                <div className="text-base font-semibold">
                  {activeContact?.full_name ?? "Select a contact"}
                </div>
                {activeContact && (
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {activeContact.title} · {activeContact.company_name}
                  </div>
                )}
                {sequence && (
                  <div className="mt-2 flex items-center gap-2 flex-wrap">
                    <StatusPill status={sequence.status} />
                    {sequence.instantly_campaign_id && (
                      <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-primary">Active via Instantly</span>
                    )}
                    {sequence.status === "simulated" && (
                      <span className="rounded bg-purple-500/15 px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-purple-400">Simulated (no Instantly key)</span>
                    )}
                  </div>
                )}
              </div>

              {/* Controls */}
              <div className="flex flex-col gap-2 items-end">
                {/* View toggle + panel toggle */}
                <div className="flex gap-2 flex-wrap justify-end">
                  <div className="flex rounded border border-border overflow-hidden text-[11px]">
                    <button
                      onClick={() => setViewMode("template")}
                      className={`flex items-center gap-1 px-2.5 py-1.5 ${viewMode === "template" ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/50"}`}
                    >
                      <Code2 className="h-3 w-3" /> Template
                    </button>
                    <button
                      onClick={() => setViewMode("preview")}
                      className={`flex items-center gap-1 px-2.5 py-1.5 ${viewMode === "preview" ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/50"}`}
                    >
                      <Eye className="h-3 w-3" /> Preview
                    </button>
                  </div>
                  <div className="flex rounded border border-border overflow-hidden text-[11px]">
                    <button
                      onClick={() => setPanelView("sequence")}
                      className={`flex items-center gap-1 px-2.5 py-1.5 ${panelView === "sequence" ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/50"}`}
                    >
                      <Wand2 className="h-3 w-3" /> Builder
                    </button>
                    <button
                      onClick={() => setPanelView("review")}
                      className={`flex items-center gap-1 px-2.5 py-1.5 ${panelView === "review" ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/50"}`}
                    >
                      <ClipboardCheck className="h-3 w-3" /> Review
                    </button>
                  </div>
                </div>

                {/* Goal / Tone / Length + Generate */}
                <div className="flex gap-2 flex-wrap justify-end">
                  <Select value={goal} onValueChange={setGoal}>
                    <SelectTrigger className="h-8 text-xs w-[130px]"><SelectValue placeholder="Goal" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Intro Call">Intro Call</SelectItem>
                      <SelectItem value="Product Demo">Product Demo</SelectItem>
                      <SelectItem value="Follow Up">Follow Up</SelectItem>
                      <SelectItem value="Re-engagement">Re-engagement</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={tone} onValueChange={setTone}>
                    <SelectTrigger className="h-8 text-xs w-[120px]"><SelectValue placeholder="Tone" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Professional">Professional</SelectItem>
                      <SelectItem value="Friendly">Friendly</SelectItem>
                      <SelectItem value="Technical">Technical</SelectItem>
                      <SelectItem value="Executive">Executive</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={seqLength.toString()} onValueChange={v => setSeqLength(Number(v))}>
                    <SelectTrigger className="h-8 text-xs w-[90px]"><SelectValue placeholder="Steps" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1 Step</SelectItem>
                      <SelectItem value="3">3 Steps</SelectItem>
                      <SelectItem value="5">5 Steps</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex gap-2 flex-wrap justify-end">
                  <Button size="sm" variant="default" disabled={selectedIds.size === 0 || isGeneratingBulk} onClick={handleGenerate}>
                    <Wand2 className="mr-2 h-4 w-4" />
                    {isGeneratingBulk ? "Generating…" : `Generate AI Sequence (${selectedIds.size})`}
                  </Button>
                  <Button size="sm" variant="secondary" disabled={!sequence || check.isPending} onClick={() => sequence && check.mutate(sequence.id)}>
                    <ShieldCheck className="mr-2 h-4 w-4" />
                    {check.isPending ? "Checking…" : "Deliverability"}
                  </Button>
                  {panelView === "sequence" && (
                    <Button size="sm" variant="secondary" disabled={!sequence || launch.isPending}
                      onClick={() => sequence && launch.mutate({ sequenceId: sequence.id, schedule })}
                      title="Launch via Instantly">
                      <Send className="mr-2 h-4 w-4" />
                      {launch.isPending ? "Launching…" : "Launch"}
                    </Button>
                  )}
                </div>
              </div>
            </div>

            {/* Deliverability report */}
            {sequence?.deliverability_report && (
              <div className="mt-4 rounded border border-border bg-background/40 p-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs uppercase tracking-widest text-muted-foreground">Deliverability</div>
                  <div className={`font-mono text-sm tabular-nums ${(sequence.deliverability_score ?? 0) >= 80 ? "text-primary" : "text-amber-400"}`}>
                    {sequence.deliverability_score?.toFixed(0)} / 100
                  </div>
                </div>
                {(sequence.deliverability_report.flagged_phrases?.length ?? 0) > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {sequence.deliverability_report.flagged_phrases!.map((p: string, i: number) => (
                      <span key={i} className="rounded bg-destructive/10 px-1.5 py-0.5 text-[10px] text-destructive">{p}</span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Card>

          {/* Generation error banner */}
          {localFallbackError && !sequence && (
            <div className="rounded border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive-foreground">
              <div className="font-semibold mb-1">AI Generation Failed</div>
              <div>Failed to generate sequence. Ensure your API keys and model limits are configured correctly.</div>
            </div>
          )}

          {/* Delivery Troubleshooting Diagnostics */}
          {sequence?.last_launch && (
            <Card className="border-card-border bg-card p-4 border-l-4 border-l-green-500">
              <div className="flex items-center justify-between mb-3">
                <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                  Delivery Diagnostics
                </div>
                <span className="text-[10px] text-muted-foreground">
                  {sequence.last_launch.timestamp
                    ? new Date(sequence.last_launch.timestamp).toLocaleString()
                    : "—"}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                <div className="space-y-0.5">
                  <div className="text-muted-foreground font-medium text-[10px] uppercase tracking-wider">Last Status</div>
                  <div className="font-semibold text-foreground text-sm">
                    {sequence.last_launch.status || "—"}
                  </div>
                </div>
                <div className="space-y-0.5">
                  <div className="text-muted-foreground font-medium text-[10px] uppercase tracking-wider">Sender</div>
                  <div className="font-mono text-foreground font-semibold truncate animate-fade-in" title={sequence.last_launch.sender || ""}>
                    {sequence.last_launch.sender || "—"}
                  </div>
                </div>
                <div className="space-y-0.5">
                  <div className="text-muted-foreground font-medium text-[10px] uppercase tracking-wider">Recipient</div>
                  <div className="font-mono text-foreground font-semibold truncate animate-fade-in" title={sequence.last_launch.recipient || ""}>
                    {sequence.last_launch.recipient || "—"}
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* ── Panel: Builder or Review ── */}
          {panelView === "review" ? (
            <ReviewPanel />
          ) : (
            <>
              {sequence ? (
                <div className="space-y-3">
                  <ReasoningPanel
                    provenance={sequence.provenance ?? undefined}
                    fallback={{
                      source: "ai_generated",
                      logic: `${sequence.steps.length}-step sequence generated by the model.`,
                      steps: [
                        "Pick channel order based on contact seniority",
                        "Prompt model for per-step subject + body with requested Goal and Tone",
                        "Schedule send_at timestamps with cumulative wait days",
                      ],
                    }}
                  />

                  {/* Template/Preview mode indicator */}
                  {viewMode === "template" && (
                    <div className="flex items-center gap-2 rounded border border-primary/30 bg-primary/5 px-3 py-2 text-xs text-primary">
                      <Code2 className="h-3 w-3 shrink-0" />
                      <span><strong>Template View</strong> — raw variables shown. Switch to Preview to see personalized content.</span>
                    </div>
                  )}

                  {sequence.steps.map((s) => (
                    <Card key={s.id} className="border-card-border bg-card p-4" data-testid={`step-${s.step_number}`}>
                      {/* Step header */}
                      <div className="mb-3 flex items-center gap-3">
                        <div className={`flex h-8 w-8 items-center justify-center rounded ${channelBg(s.channel)}`}>
                          {channelIcon(s.channel)}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-muted-foreground">
                            <span>Step {s.step_number} · {editingStepId === s.id ? editDraft.channel : s.channel}</span>
                            <SourceBadge source="ai_generated" />
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {editingStepId !== s.id && (
                            <div className="text-right text-[11px] text-muted-foreground">
                              Wait {s.wait_days}d · {fmtDate(s.send_at)}
                            </div>
                          )}
                          {editingStepId === s.id ? (
                            <button onClick={() => setEditingStepId(null)} className="rounded p-1 text-muted-foreground hover:text-foreground" title="Cancel edit">
                              <X className="h-4 w-4" />
                            </button>
                          ) : (
                            <button onClick={() => startEditStep(s.id)} className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground" title="Edit step">
                              <Pencil className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </div>

                      {editingStepId === s.id ? (
                        /* ── Inline edit mode ── */
                        <div className="space-y-3 border-t border-border pt-3">
                          <div className="grid grid-cols-3 gap-3">
                            <div>
                              <Label className="text-xs">Channel</Label>
                              <Select value={editDraft.channel} onValueChange={v => setEditDraft({ ...editDraft, channel: v as any })}>
                                <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="email">Email</SelectItem>
                                  <SelectItem value="linkedin">LinkedIn</SelectItem>
                                  <SelectItem value="call">Call</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <Label className="text-xs">Wait days</Label>
                              <Input type="number" min={0} value={editDraft.wait_days}
                                onChange={e => setEditDraft({ ...editDraft, wait_days: Number(e.target.value) })}
                                className="h-8 text-xs" />
                            </div>
                            <div className="col-span-1 flex items-end">
                              <div className="rounded-md bg-muted/50 border border-border px-3 py-1.5 text-[10px] text-muted-foreground leading-snug">
                                ⏰ Sending window set at campaign level
                              </div>
                            </div>
                          </div>
                          {editDraft.channel !== "call" && (
                            <div>
                              <Label className="text-xs">Subject</Label>
                              <Input value={editDraft.subject} onChange={e => setEditDraft({ ...editDraft, subject: e.target.value })} className="text-sm" />
                            </div>
                          )}
                          <div>
                            <Label className="text-xs">Body</Label>
                            <Textarea value={editDraft.body} rows={7} onChange={e => setEditDraft({ ...editDraft, body: e.target.value })} className="text-sm" />
                          </div>
                          <div className="flex items-center gap-2">
                            <Button size="sm" onClick={saveStep} disabled={patchStep.isPending} className="h-7 text-xs">
                              {patchStep.isPending ? "Saving…" : "Save changes"}
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setEditingStepId(null)} className="h-7 text-xs">Cancel</Button>
                          </div>
                        </div>
                      ) : (
                        /* ── Read-only step view ── */
                        <div className="space-y-2 border-t border-border pt-3">
                          {/* Subject — always shown */}
                          <div>
                            <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-0.5">Subject</div>
                            <div className="text-sm font-medium">{renderSubject(s.subject, s.channel)}</div>
                          </div>
                          {/* Body — always shown */}
                          <div>
                            <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-0.5">Body</div>
                            <div className="whitespace-pre-wrap rounded border border-border bg-background/40 p-3 text-sm text-foreground/90">
                              {renderBody(s.body || "")}
                            </div>
                          </div>
                          {/* Wait — always shown */}
                          <div className="text-[11px] text-muted-foreground">
                            Wait: {s.wait_days} {s.wait_days === 1 ? "day" : "days"} · Scheduled: {fmtDate(s.send_at) || "—"}
                          </div>
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              ) : (
                /* ── Empty state: placeholder cards ── */
                <div className="space-y-3">
                  <div className="rounded border border-dashed border-border px-4 py-3 flex items-center justify-between gap-4">
                    <p className="text-sm text-muted-foreground">
                      {contacts?.length
                        ? "No sequence drafted yet. Select contacts, choose your goal and tone, then click Generate."
                        : "Loading contacts…"}
                    </p>
                    {contacts && contacts.length > 0 && (
                      <Button size="sm" disabled={selectedIds.size === 0 || isGeneratingBulk} onClick={handleGenerate}>
                        <Wand2 className="mr-2 h-4 w-4" />
                        {isGeneratingBulk ? "Generating…" : "Generate Sequence"}
                      </Button>
                    )}
                  </div>

                  {PLACEHOLDER_STEPS.map(ph => (
                    <Card key={ph.step} className="border-card-border bg-card/50 p-4 opacity-60">
                      <div className="mb-3 flex items-center gap-3">
                        <div className={`flex h-8 w-8 items-center justify-center rounded ${channelBg(ph.channel)}`}>
                          {channelIcon(ph.channel)}
                        </div>
                        <div className="flex-1">
                          <div className="text-xs uppercase tracking-widest text-muted-foreground">
                            Step {ph.step} · {ph.channel}
                          </div>
                        </div>
                        <div className="text-[11px] text-muted-foreground">Wait {ph.wait}d</div>
                      </div>
                      <div className="space-y-2 border-t border-border pt-3">
                        <div>
                          <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-0.5">Subject</div>
                          <div className="text-sm italic text-muted-foreground">{ph.subject}</div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-0.5">Body</div>
                          <div className="rounded border border-border border-dashed p-3 text-sm italic text-muted-foreground">{ph.body}</div>
                        </div>
                        <div className="text-[11px] text-muted-foreground">Wait: {ph.wait} days</div>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
