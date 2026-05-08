import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/PageHeader";
import { TierBadge, StatusPill } from "@/components/Pills";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { useContacts } from "@/hooks/useContacts";
import {
  useSequenceByContact,
  useGenerateSequence,
  useDeliverabilityCheck,
  useLaunchSequence,
} from "@/hooks/useSequences";
import { Mail, Linkedin, Phone, ShieldCheck, Send, Wand2 } from "lucide-react";
import { fmtDate } from "@/lib/format";
import { ReasoningPanel, SourceBadge } from "@/components/ReasoningPanel";

export function Outreach() {
  const { active, activeId } = useActiveStrategy();
  const { data: contacts } = useContacts(activeId ?? undefined, 1);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (!selected && contacts && contacts[0]) setSelected(contacts[0].id);
  }, [contacts, selected]);

  const { data: sequence } = useSequenceByContact(selected ?? undefined);
  const generate = useGenerateSequence();
  const check = useDeliverabilityCheck();
  const launch = useLaunchSequence();

  const contact = contacts?.find((c) => c.id === selected);

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
        subtitle={`Persona-aware sequences for top-tier contacts in ${active?.product_name ?? ""}.`}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-4 border-card-border bg-card p-3">
          <div className="mb-2 px-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Tier 1 contacts
          </div>
          <div className="space-y-1">
            {contacts?.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelected(c.id)}
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
            {(!contacts || contacts.length === 0) && (
              <div className="px-3 py-6 text-center text-xs text-muted-foreground">
                No Tier 1 contacts yet.
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
                <Button
                  size="sm"
                  disabled={!sequence || launch.isPending}
                  onClick={() => sequence && launch.mutate(sequence.id)}
                  data-testid="button-launch"
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
                {sequence.deliverability_report.flagged_phrases?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {sequence.deliverability_report.flagged_phrases.map(
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
                  logic: `4-step ${sequence.steps.some((s) => s.channel === "linkedin" && s.step_number === 1) ? "LinkedIn-first" : "email-first"} sequence generated by the model from the contact's persona profile and the strategy's top use cases. Deliverability score is computed deterministically from spam-trigger phrases, message length, and link count.`,
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
                  <div className="mb-2 flex items-center gap-3">
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
                        <span>Step {s.step_number} · {s.channel}</span>
                        <SourceBadge source="ai_generated" />
                      </div>
                      <div className="text-sm font-medium">
                        {s.subject || (s.channel === "call" ? "Call talking points" : "(no subject)")}
                      </div>
                    </div>
                    <div className="text-right text-[11px] text-muted-foreground">
                      Wait {s.wait_days}d · {fmtDate(s.send_at)}
                    </div>
                  </div>
                  <div className="whitespace-pre-wrap rounded border border-border bg-background/40 p-3 text-sm text-foreground/90">
                    {s.body || "—"}
                  </div>
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
