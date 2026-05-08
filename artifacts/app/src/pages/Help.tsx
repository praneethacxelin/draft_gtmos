import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/PageHeader";
import {
  Compass,
  Users,
  Send,
  Activity,
  Settings as SettingsIcon,
  ArrowRight,
  Zap,
  Search,
  Radar,
  Sparkles,
  Brain,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Lightbulb,
  Target,
  TrendingUp,
  Database,
} from "lucide-react";

export function Help() {
  return (
    <>
      <PageHeader
        eyebrow="Reference"
        title="Help & Solution Guide"
        subtitle="How to use Agentic GTM Factory, and the reasoning behind every stage of the pipeline."
      />

      <Tabs defaultValue="how-to-use" className="space-y-6">
        <TabsList>
          <TabsTrigger value="how-to-use">How to Use</TabsTrigger>
          <TabsTrigger value="solution-architecture">Solution Architecture</TabsTrigger>
        </TabsList>

        <TabsContent value="how-to-use" className="space-y-4">
          <HowToUse />
        </TabsContent>

        <TabsContent value="solution-architecture" className="space-y-6">
          <SolutionArchitecture />
        </TabsContent>
      </Tabs>
    </>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.2em] text-muted-foreground">
      {children}
    </div>
  );
}

function CalloutCard({
  icon,
  label,
  children,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        accent
          ? "border-primary/30 bg-primary/5"
          : "border-border bg-card"
      }`}
    >
      <div className="mb-2 flex items-center gap-2">
        <span className={accent ? "text-primary" : "text-muted-foreground"}>
          {icon}
        </span>
        <span className="text-xs font-semibold uppercase tracking-widest text-foreground">
          {label}
        </span>
      </div>
      <div className="text-sm text-muted-foreground leading-relaxed">
        {children}
      </div>
    </div>
  );
}

const HOW_TO_STEPS = [
  {
    number: "01",
    icon: <Compass className="h-5 w-5" />,
    stage: "Strategy",
    eyebrow: "Stage 1",
    what: "Define your go-to-market brief. Tell the system what you sell, who you sell to, and what pain points you solve.",
    actions: [
      'Click "New Strategy" from the Dashboard or the Strategy page.',
      "Fill in product name, description, target market, and pain points.",
      'Hit "Generate" — the AI builds your ICP, persona profiles, NAICS codes, use cases, and problem statements in one run.',
    ],
    output: "A fully structured strategy with ideal customer profile, persona cards, and scored problem areas — ready to drive prospecting.",
    next: "Go to Prospects → run lead discovery.",
  },
  {
    number: "02",
    icon: <Users className="h-5 w-5" />,
    stage: "Prospects",
    eyebrow: "Stage 2",
    what: "Find the right accounts and contacts, detect buying signals, and score every lead so you know who to call first.",
    actions: [
      '"Discover leads" — pulls contacts from Apollo (or AI demo if no API key).',
      '"Run signals" — scans for funding rounds, hiring sprees, and tech-stack changes at each account.',
      '"Score leads" — combines ICP fit, signal strength, and engagement into a Tier 1 / 2 / 3 ranking.',
      '"Recognize patterns" — uses historical data to boost contacts that match your best past wins.',
    ],
    output: "Tiered contact list with ICP-fit scores, signal scores, and engagement scores. Tier 1 contacts go straight to Outreach.",
    next: "Switch to the Outreach tab to draft sequences.",
  },
  {
    number: "03",
    icon: <Send className="h-5 w-5" />,
    stage: "Outreach",
    eyebrow: "Stage 3",
    what: "Generate and launch personalised, multi-channel sequences for every contact — email, LinkedIn, and phone — in one click.",
    actions: [
      "Pick a contact from the left-hand panel (any tier is accessible).",
      '"Generate" — the model writes a 4-step sequence grounded in the contact\'s persona and your strategy\'s top use cases.',
      '"Deliverability" — checks the draft for spam triggers and gives a score out of 100.',
      '"Launch" — pushes to Instantly (or simulates a send if no Instantly key is configured).',
    ],
    output: "A personalised 4-step email/LinkedIn/call sequence per contact, with a deliverability score and send schedule.",
    next: "Track replies and engagement in Intelligence.",
  },
  {
    number: "04",
    icon: <Activity className="h-5 w-5" />,
    stage: "Intelligence",
    eyebrow: "Stage 4",
    what: "Close the feedback loop. See who's engaging, score intent, qualify leads into MQL/SQL buckets, and let the AI refine your ICP.",
    actions: [
      '"Recompute" in the Intent tab — recalculates account-level intent scores from all engagement events.',
      "Submit feedback in the Feedback tab — paste in call notes, emails, or meeting summaries and the AI extracts themes.",
      '"Qualify" next to a contact — generates a champion/economic-buyer/blocker classification and rationale.',
      '"Apply" in the Loop-back tab — updates your strategy\'s ICP based on all accumulated signals.',
    ],
    output: "Intent-scored accounts, MQL/SQL-qualified contacts, and an auto-refined ICP that gets sharper over time.",
    next: "Return to Prospects to re-run scoring with the updated ICP.",
  },
  {
    number: "05",
    icon: <SettingsIcon className="h-5 w-5" />,
    stage: "Settings",
    eyebrow: "Configuration",
    what: "Connect live data sources and tune the fetch caps that govern how many records each agent run pulls.",
    actions: [
      "Add an Apollo API key to switch from AI-demo contacts to real people-search.",
      "Add a SerpAPI key to replace synthetic signals with live funding and hiring events.",
      "Add an Instantly API key to launch real email campaigns instead of simulations.",
      "Adjust the per-deployment fetch sliders (Leads per run / Signals per account / Market sizing results) to protect your free-tier quotas.",
    ],
    output: "All agent runs switch from demo/AI-generated data to live external data. Fetch caps prevent runaway API spend.",
    next: "Go back to Prospects and run a full live cycle.",
  },
];

function HowToUse() {
  return (
    <div className="space-y-4">
      <CalloutCard icon={<Lightbulb className="h-4 w-4" />} label="Quick start">
        GTM Factory runs as a linear pipeline: define your strategy first, then discover prospects, then draft outreach, then
        track intelligence. Each stage feeds the next. You can re-run any stage as many times as you like — the system
        gets smarter each cycle.
      </CalloutCard>

      <div className="space-y-4">
        {HOW_TO_STEPS.map((step, i) => (
          <Card key={i} className="border-card-border bg-card p-5">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                {step.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="mb-0.5 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  {step.eyebrow}
                </div>
                <div className="text-base font-semibold text-foreground">{step.stage}</div>
                <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{step.what}</p>

                <div className="mt-3 space-y-1.5">
                  {step.actions.map((a, j) => (
                    <div key={j} className="flex items-start gap-2 text-sm">
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                      <span className="text-foreground/80">{a}</span>
                    </div>
                  ))}
                </div>

                <div className="mt-3 rounded-md border border-border bg-background/60 px-3 py-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Output: </span>{step.output}
                </div>

                <div className="mt-3 flex items-center gap-2 text-xs text-primary">
                  <ArrowRight className="h-3.5 w-3.5" />
                  <span>{step.next}</span>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

const PIPELINE_STAGES = [
  {
    id: "S1",
    label: "Strategy & Discovery",
    color: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    dotColor: "bg-blue-400",
    trigger: "User submits a new strategy brief",
    input: "Product name, description, target market, pain points",
    agent: "S1 LangGraph (ICP → Personas → Problems → NAICS → Stakeholders → Use Cases → Embed)",
    output: "Structured ICP profile, 2-4 persona cards, scored problem statements, NAICS industry codes, pgvector embedding",
    why: "You can't find the right people without knowing who they are. The ICP and personas become the scoring rubric for every subsequent lead.",
    icon: <Brain className="h-4 w-4" />,
  },
  {
    id: "S2",
    label: "Prospecting & Scoring",
    color: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    dotColor: "bg-amber-400",
    trigger: "User clicks Discover Leads, Run Signals, or Score Leads",
    input: "S1 ICP + persona profiles, Apollo / SerpAPI credentials (or AI demo), fetch-limit caps",
    agent: "S2 Signals (lead discovery → signal detection → composite scoring → pgvector pattern boost)",
    output: "Accounts with intent scores, Tier 1/2/3 contacts with composite scores (ICP fit + signals + engagement + pattern boost)",
    why: "Raw leads are noise. Scoring with four weighted dimensions surfaces the contacts most likely to convert — and it gets more accurate every cycle as the M3 loop feeds back engagement data.",
    icon: <Search className="h-4 w-4" />,
  },
  {
    id: "S3",
    label: "Outreach Sequencing",
    color: "bg-primary/15 text-primary border-primary/30",
    dotColor: "bg-primary",
    trigger: "User clicks Generate for a contact",
    input: "Contact persona + seniority, strategy use cases, channel-plan heuristic (email-first vs LinkedIn-first)",
    agent: "S3 Outreach (channel plan → model-generated subject + body per step → deliverability check → Instantly push)",
    output: "4-step personalised sequence (email / LinkedIn / call mix), deliverability score, persisted SequenceStep rows",
    why: "Personalisation at scale is impossible manually. The model grounds each message in the contact's specific role and your strategy's top use cases — not generic templates.",
    icon: <Send className="h-4 w-4" />,
  },
  {
    id: "M3",
    label: "Intelligence Loop",
    color: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    dotColor: "bg-purple-400",
    trigger: "User submits feedback, clicks Recompute, Qualify, or Apply Loop-back",
    input: "Engagement events, feedback text, contact qualification state, current ICP",
    agent: "M3 Intent (intent scoring → feedback extraction → contact qualification → ICP loop-back via model)",
    output: "Updated account intent scores, extracted feedback themes, champion/blocker classifications, refined ICP suggestions",
    why: "Every outreach run generates signal. M3 harvests that signal — who opened, replied, pushed back — and feeds it back into S2 scoring and S1 ICP. Each cycle tightens the targeting.",
    icon: <RotateCcw className="h-4 w-4" />,
  },
];

function SolutionArchitecture() {
  return (
    <div className="space-y-8">
      <section>
        <SectionLabel>Product objective</SectionLabel>
        <Card className="border-card-border bg-card p-5">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Target className="h-5 w-5" />
            </div>
            <div>
              <div className="text-base font-semibold text-foreground">
                Eliminate the manual GTM grind for B2B sales teams
              </div>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                Most GTM teams spend 60–70% of their time on work that doesn't require human judgement: researching
                companies, drafting sequences, tracking replies, and updating CRMs. GTM Factory automates that entire
                layer. A sales rep or founder describes their product once; the system builds the ICP, finds the right
                accounts, generates personalised outreach, and continuously sharpens its own targeting based on what
                actually converts.
              </p>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                <span className="font-medium text-foreground">Who it's for:</span> Early-stage founders running outbound
                themselves, small SDR teams without RevOps infrastructure, and GTM leaders who want a living data layer
                beneath their CRM.
              </p>
            </div>
          </div>
        </Card>
      </section>

      <section>
        <SectionLabel>Stage-by-stage journey map</SectionLabel>
        <div className="space-y-3">
          {PIPELINE_STAGES.map((stage, i) => (
            <div key={stage.id}>
              <Card className={`border bg-card p-5 ${stage.color.split(" ")[2]}`}>
                <div className="mb-3 flex items-center gap-3">
                  <div className={`flex h-8 w-8 items-center justify-center rounded-md border ${stage.color}`}>
                    {stage.icon}
                  </div>
                  <div>
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ${stage.color}`}>
                      {stage.id}
                    </span>
                    <span className="ml-2 text-sm font-semibold text-foreground">{stage.label}</span>
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-3 text-xs md:grid-cols-2">
                  <div>
                    <div className="mb-1 font-semibold uppercase tracking-widest text-muted-foreground">Trigger</div>
                    <div className="text-foreground/80">{stage.trigger}</div>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold uppercase tracking-widest text-muted-foreground">Input</div>
                    <div className="text-foreground/80">{stage.input}</div>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold uppercase tracking-widest text-muted-foreground">Agent / logic</div>
                    <div className="text-foreground/80">{stage.agent}</div>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold uppercase tracking-widest text-muted-foreground">Output</div>
                    <div className="text-foreground/80">{stage.output}</div>
                  </div>
                </div>
                <div className="mt-3 rounded border border-border bg-background/50 px-3 py-2 text-xs">
                  <span className="font-semibold text-foreground">Why this runs here: </span>
                  <span className="text-muted-foreground">{stage.why}</span>
                </div>
              </Card>
              {i < PIPELINE_STAGES.length - 1 && (
                <div className="flex justify-center py-1">
                  <ArrowRight className="h-4 w-4 rotate-90 text-muted-foreground" />
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <SectionLabel>Why the trigger sequence is correct</SectionLabel>
        <Card className="border-card-border bg-card p-5 space-y-4">
          {[
            {
              icon: <CheckCircle2 className="h-4 w-4 text-primary" />,
              title: "Strategy before Prospects",
              body: "Lead scoring requires a rubric. Without a defined ICP, every contact looks equally good (or bad). S1 produces the scoring criteria — seniority keywords, persona types, pain-point keywords — that S2 uses to rank every contact. Running S2 without S1 would produce random tiers.",
            },
            {
              icon: <CheckCircle2 className="h-4 w-4 text-primary" />,
              title: "Signals before Scoring",
              body: "Signal score carries 40% of the composite total — it's the strongest weight. Running score_leads before run_signals means signal_score = 0 for every contact, which would demote high-intent accounts and bias the tier list. Signals must arrive before scoring runs.",
            },
            {
              icon: <CheckCircle2 className="h-4 w-4 text-primary" />,
              title: "Scoring before Outreach",
              body: "Outreach is expensive in time and sender reputation. Launching a sequence to an unscored list means you're emailing every contact with equal priority. Tier-ranking ensures the highest-value contacts get the most personalised treatment first.",
            },
            {
              icon: <CheckCircle2 className="h-4 w-4 text-primary" />,
              title: "Outreach before Intelligence",
              body: "M3 can only score intent if there are engagement events to process. Until sequences are launched and replies/opens tracked, intent recomputation returns empty results. Intelligence is the trailing loop — it requires outreach data to function.",
            },
            {
              icon: <CheckCircle2 className="h-4 w-4 text-primary" />,
              title: "Intelligence feeds back to S1 + S2",
              body: "The M3 loop-back writes refined ICP suggestions back to the strategy. Re-running S2 scoring after an M3 cycle means the new weights (e.g. 'champion-type contacts convert 2× more') are baked into the next tier ranking. Each full cycle is more accurate than the last.",
            },
          ].map((item, i) => (
            <div key={i} className="flex items-start gap-3">
              <span className="mt-0.5 shrink-0">{item.icon}</span>
              <div>
                <div className="text-sm font-semibold text-foreground">{item.title}</div>
                <div className="mt-0.5 text-sm text-muted-foreground leading-relaxed">{item.body}</div>
              </div>
            </div>
          ))}
        </Card>
      </section>

      <section>
        <SectionLabel>Worked example</SectionLabel>
        <Card className="border-primary/20 bg-primary/5 p-5">
          <div className="mb-3 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold text-foreground">
              A VP Sales at a Series B healthcare SaaS company — from zero to first touch
            </span>
          </div>
          <div className="space-y-3">
            {[
              {
                step: "Strategy",
                detail: 'Founder fills in: "ClinicPulse — patient engagement platform for independent dental practices, pain: missed appointments and poor recall rates." S1 generates ICP (SMB dental practice, 1-5 providers, <$2M revenue), persona "Champion = Office Manager", NAICS 621210.',
              },
              {
                step: "Lead Discovery",
                detail: 'Apollo search returns Dr. Emily Zhang, Cardiologist/Founder at Heart Specialty Group. ICP fit: title present (+10), Founder seniority (+20), persona_type = champion (+10) → icp_fit_score = 90.',
              },
              {
                step: "Signal Detection",
                detail: 'SerpAPI query "Heart Specialty Group raises funding" returns a Series A press release. strength_score = 0.7 → signal_score = 17.5. Second query "Heart Specialty Group hiring VP Sales" returns two job posts → +35. Total signal_score = 52.5.',
              },
              {
                step: "Scoring",
                detail: 'total = (90 × 0.30) + (52.5 × 0.40) + (0 × 0.30) + 0 = 27 + 21 = 48. With the pattern boost from two recognized clusters: 48 + 10 = 58 → Tier 1.',
              },
              {
                step: "Outreach",
                detail: 'Seniority = Founder → LinkedIn-first plan. Model writes: Step 1 LinkedIn DM referencing the Series A and asking about patient recall, Step 2 email with a dental-specific ROI framing, Step 3 follow-up email, Step 4 call talking points. Deliverability score: 91/100.',
              },
              {
                step: "Intelligence",
                detail: 'Dr. Zhang opens Step 2 email twice → engagement event added. M3 intent recompute: engagement_score = 40. Next scoring pass: total = 27 + 21 + 12 = 60 → still Tier 1, urgency upgraded to "high". SDR Copilot surfaces her at the top of Today\'s top plays.',
              },
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3 text-sm">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/20 text-[10px] font-bold text-primary">
                  {i + 1}
                </span>
                <div>
                  <span className="font-semibold text-foreground">{item.step}: </span>
                  <span className="text-muted-foreground">{item.detail}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section>
        <SectionLabel>Key solutions at each step</SectionLabel>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {[
            {
              icon: <Brain className="h-4 w-4" />,
              label: "LangGraph multi-node pipeline (S1)",
              body: "Each ICP section (personas, problems, NAICS, use cases) runs as its own graph node. This means future versions can add per-node retries, human-in-the-loop checkpoints, or conditional routing without touching the rest of the flow.",
            },
            {
              icon: <Database className="h-4 w-4" />,
              label: "pgvector similarity scoring",
              body: "Strategy embeddings are stored in PostgreSQL with pgvector. When patterns are recognised, the system compares your new strategy's embedding against historical 'hot' clusters — boosting contacts that match past winners by up to 15 points.",
            },
            {
              icon: <Radar className="h-4 w-4" />,
              label: "Token-bucket rate limiting",
              body: "Every call to OpenAI, SerpAPI, Apollo, and Instantly goes through a shared in-process token bucket. Burst traffic gets queued (up to 2s) before returning a friendly 429 — protecting free-tier quotas without crashing agent runs.",
            },
            {
              icon: <Zap className="h-4 w-4" />,
              label: "Composite scoring with four weights",
              body: "ICP fit (30%) + signal score (40%) + engagement (30%) + pattern boost (max +15). Signals carry the most weight because buying intent (funding round, hiring spree) is the strongest leading indicator of conversion readiness.",
            },
            {
              icon: <Send className="h-4 w-4" />,
              label: "Persona-aware channel selection",
              body: "The outreach agent picks email-first or LinkedIn-first based on the contact's seniority. Founders and VPs get LinkedIn DMs first (higher response rate on LinkedIn); individual contributors get email-first. This heuristic is surfaced transparently on every step card.",
            },
            {
              icon: <TrendingUp className="h-4 w-4" />,
              label: "M3 intelligence loop-back",
              body: "After enough engagement and feedback accumulates, the loop-back agent asks the model to compare actual responders vs non-responders and suggest ICP refinements. Those suggestions are applied to the strategy and trickle down to the next scoring run.",
            },
          ].map((item, i) => (
            <Card key={i} className="border-card-border bg-card p-4">
              <div className="mb-2 flex items-center gap-2">
                <span className="text-primary">{item.icon}</span>
                <span className="text-xs font-semibold text-foreground">{item.label}</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{item.body}</p>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <SectionLabel>What comes next</SectionLabel>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {[
            {
              icon: <AlertCircle className="h-4 w-4" />,
              label: "Live API keys",
              body: "Add Apollo, SerpAPI, and Instantly keys in Settings to switch from AI-demo data to real people-search, live buying signals, and actual email sends.",
            },
            {
              icon: <Send className="h-4 w-4" />,
              label: "Multi-channel automation",
              body: "Automatically execute every step of a sequence — LinkedIn DMs, emails, and call reminders — on a schedule, without the rep needing to log in and hit Launch each time.",
            },
            {
              icon: <Database className="h-4 w-4" />,
              label: "CRM sync",
              body: "Push scored contacts and sequence outcomes directly to HubSpot or Salesforce so your GTM motion lives alongside your existing sales process.",
            },
            {
              icon: <Users className="h-4 w-4" />,
              label: "Team collaboration",
              body: "Allow multiple reps to share a strategy, own different contact segments, and see each other's outreach in a unified feed.",
            },
            {
              icon: <TrendingUp className="h-4 w-4" />,
              label: "RevenueCat gating",
              body: "Gate advanced features (unlimited strategies, live API connections, team seats) behind a subscription tier managed via RevenueCat — so the free plan stays generous while power users unlock the full pipeline.",
            },
            {
              icon: <TrendingUp className="h-4 w-4" />,
              label: "Conversion analytics",
              body: "Track reply rates, meeting-booked rates, and revenue influenced per sequence — so you can see which persona + channel combination performs best.",
            },
          ].map((item, i) => (
            <div
              key={i}
              className="flex items-start gap-3 rounded-lg border border-border bg-card p-4"
            >
              <span className="mt-0.5 text-muted-foreground">{item.icon}</span>
              <div>
                <div className="text-sm font-semibold text-foreground">{item.label}</div>
                <div className="mt-0.5 text-xs text-muted-foreground leading-relaxed">{item.body}</div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
