import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { apiFetch } from "@/lib/api";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronRight,
  ChevronLeft,
  Save,
  Check,
  Building2,
  Target,
  Users,
  Zap,
  DollarSign,
  Sparkles,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Question definitions                                              */
/* ------------------------------------------------------------------ */

export type QuestionType = "text" | "textarea" | "mcq" | "mcq_multi";

export interface QuestionDef {
  id: string;
  title: string;
  desc: string;
  type: QuestionType;
  options?: string[];
  placeholder?: string;
  rows?: number;
}

interface Section {
  id: string;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  questions: QuestionDef[];
}

const SECTIONS: Section[] = [
  {
    id: "basics",
    title: "Product & Company",
    subtitle: "Tell us about what you offer",
    icon: <Building2 className="h-4 w-4" />,
    questions: [
      {
        id: "product_description",
        title: "What is your product or service?",
        desc: "A brief description of what it does, who it's for, and the core problem it solves.",
        type: "textarea",
        placeholder: "e.g., An AI-powered sales intelligence platform that helps B2B sales teams find and prioritize high-intent buyers…",
        rows: 3,
      },
      {
        id: "company_type",
        title: "What type of company are you?",
        desc: "Select the category that best describes your business model.",
        type: "mcq",
        options: [
          "SaaS",
          "Consulting / Agency",
          "E-commerce / D2C",
          "Marketplace / Platform",
          "Hardware + Software",
          "Services / Professional",
          "IT / Managed Services",
        ],
      },
      {
        id: "pain_points",
        title: "What pain points does your product solve?",
        desc: "What hurts today for the buyer? Be specific.",
        type: "textarea",
        placeholder: "e.g., Sales teams waste 60% of their time on unqualified leads. No visibility into who is actively in-market…",
        rows: 3,
      },
    ],
  },
  {
    id: "customer",
    title: "Ideal Customer",
    subtitle: "Who are you trying to reach?",
    icon: <Target className="h-4 w-4" />,
    questions: [
      {
        id: "org_size",
        title: "What org size are you targeting?",
        desc: "Select all that apply.",
        type: "mcq_multi",
        options: [
          "1–10 (Startup)",
          "11–50 (Small)",
          "51–200 (Mid-Market)",
          "201–1,000 (Enterprise)",
          "1,000+ (Large Enterprise)",
        ],
      },
      {
        id: "target_geos",
        title: "What geographies are you targeting?",
        desc: "Select all that apply.",
        type: "mcq_multi",
        options: [
          "North America",
          "Europe",
          "India",
          "Asia-Pacific",
          "Latin America",
          "Middle East & Africa",
          "Global",
        ],
      },
      {
        id: "perfect_customer",
        title: "Describe your perfect customer",
        desc: "What does an ideal company look like? Industry, stage, tech stack, culture, etc.",
        type: "textarea",
        placeholder: "e.g., Series B+ SaaS companies with 100-500 employees, using Salesforce, actively hiring SDRs, in North America…",
        rows: 3,
      },
    ],
  },
  {
    id: "buying",
    title: "Buying Committee",
    subtitle: "Who's involved in the decision?",
    icon: <Users className="h-4 w-4" />,
    questions: [
      {
        id: "economic_buyer",
        title: "Who is the Economic Buyer?",
        desc: "The person with the budget and final say. What's their typical title?",
        type: "text",
        placeholder: "e.g., VP of Sales, CRO, Head of Revenue",
      },
      {
        id: "champion",
        title: "Who is the Champion?",
        desc: "The person who drives this internally and feels the problem first.",
        type: "text",
        placeholder: "e.g., Sales Manager, RevOps Lead, SDR Manager",
      },
      {
        id: "deal_blockers",
        title: "What typically blocks deals?",
        desc: "Select the most common blockers.",
        type: "mcq_multi",
        options: [
          "IT / Security (compliance)",
          "Finance / Procurement (cost)",
          "Legal (contract / data)",
          "End Users (adoption resistance)",
          "Existing Vendor Loyalty",
          "Long internal approval chains",
        ],
      },
    ],
  },
  {
    id: "signals",
    title: "Signals & Competition",
    subtitle: "What to look for and who you're up against",
    icon: <Zap className="h-4 w-4" />,
    questions: [
      {
        id: "buying_signals",
        title: "What buying signals should we look for?",
        desc: "Select triggers that indicate a company is ready to buy.",
        type: "mcq_multi",
        options: [
          "Just raised funding",
          "Hired new leadership (VP / C-level)",
          "Expanding to new markets",
          "Tech stack migration",
          "Competitor contract renewal",
          "Job postings for related roles",
          "Negative reviews of competitor",
        ],
      },
      {
        id: "triggers",
        title: "What triggers a purchase?",
        desc: "What pain gets so bad they have to act?",
        type: "textarea",
        placeholder: "e.g., Missed quarterly revenue targets, board pressure to reduce CAC, key competitor just launched a similar feature…",
        rows: 2,
      },
      {
        id: "alternatives",
        title: "What tools / methods do they currently use?",
        desc: "Knowing current tools helps us find lookalike leads using those technologies.",
        type: "text",
        placeholder: "e.g., Spreadsheets, ZoomInfo, LinkedIn Sales Navigator, HubSpot",
      },
      {
        id: "uvp",
        title: "What is your unique value proposition?",
        desc: "Why do you win over competitors?",
        type: "textarea",
        placeholder: "e.g., 3x faster lead qualification with AI-driven intent signals at half the cost of ZoomInfo…",
        rows: 2,
      },
      {
        id: "sales_cycle",
        title: "What is the typical sales cycle?",
        desc: "How long from first contact to close?",
        type: "mcq",
        options: [
          "< 1 month",
          "1–3 months",
          "3–6 months",
          "6–12 months",
          "12+ months",
        ],
      },
    ],
  },
  {
    id: "roi",
    title: "Investment & ROI",
    subtitle: "What you'll invest and expect back",
    icon: <DollarSign className="h-4 w-4" />,
    questions: [
      {
        id: "planned_investment",
        title: "What is your planned GTM investment?",
        desc: "Total budget for this go-to-market motion (tools, people, ads, etc.). Enter a dollar amount.",
        type: "text",
        placeholder: "e.g., $250,000",
      },
      {
        id: "expected_revenue",
        title: "What revenue / return do you expect from it?",
        desc: "The revenue you expect this investment to generate over the timeframe below.",
        type: "text",
        placeholder: "e.g., $1,500,000",
      },
      {
        id: "roi_timeframe",
        title: "Over what timeframe?",
        desc: "The window in which you expect to realize that return.",
        type: "mcq",
        options: [
          "3 months",
          "6 months",
          "12 months",
          "18 months",
          "24 months",
          "36 months",
        ],
      },
    ],
  },
];

const ALL_QUESTIONS = SECTIONS.flatMap((s) => s.questions);

/* ------------------------------------------------------------------ */
/*  Hook                                                              */
/* ------------------------------------------------------------------ */

export function useUpdateDiscovery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      apiFetch(`/api/strategies/${id}/discovery`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: (_, variables) => {
      qc.invalidateQueries({ queryKey: ["strategy", variables.id] });
    },
  });
}

/* ------------------------------------------------------------------ */
/*  MCQ Chip Component                                                */
/* ------------------------------------------------------------------ */

function McqChips({
  options,
  value,
  multi,
  onChange,
}: {
  options: string[];
  value: string | string[];
  multi: boolean;
  onChange: (val: string | string[]) => void;
}) {
  const selected: string[] = Array.isArray(value)
    ? value
    : value
      ? [value]
      : [];
  const otherVal =
    selected.find((s) => !options.includes(s) && s !== "__other__") || "";
  const hasOther = selected.includes("__other__") || otherVal !== "";

  function toggle(opt: string) {
    if (multi) {
      const next = selected.includes(opt)
        ? selected.filter((s) => s !== opt)
        : [...selected, opt];
      onChange(next);
    } else {
      onChange(selected.includes(opt) ? "" : opt);
    }
  }

  function toggleOther() {
    if (multi) {
      if (hasOther) {
        const next = selected.filter(
          (s) => s !== "__other__" && options.includes(s),
        );
        onChange(next);
      } else {
        onChange([...selected, "__other__"]);
      }
    } else {
      onChange(hasOther ? "" : "__other__");
    }
  }

  function setOtherText(text: string) {
    if (multi) {
      const base = selected.filter(
        (s) => s !== "__other__" && options.includes(s),
      );
      if (text) {
        onChange([...base, text]);
      } else {
        onChange([...base, "__other__"]);
      }
    } else {
      onChange(text || "__other__");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className={`mcq-chip ${selected.includes(opt) ? "mcq-chip--selected" : ""}`}
          >
            {selected.includes(opt) && (
              <Check className="mr-1.5 h-3 w-3 shrink-0" />
            )}
            {opt}
          </button>
        ))}
        <button
          type="button"
          onClick={toggleOther}
          className={`mcq-chip ${hasOther ? "mcq-chip--selected" : ""}`}
        >
          {hasOther && <Check className="mr-1.5 h-3 w-3 shrink-0" />}
          Other
        </button>
      </div>
      {hasOther && (
        <Input
          value={otherVal}
          onChange={(e) => setOtherText(e.target.value)}
          placeholder="Please specify…"
          className="mt-2 max-w-md bg-background/50"
          autoFocus
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Wizard Component                                                  */
/* ------------------------------------------------------------------ */

export function DiscoveryWizard({
  strategyId,
  initialData,
  onComplete,
}: {
  strategyId: string;
  initialData?: any;
  onComplete?: () => void;
}) {
  const [data, setData] = useState<Record<string, any>>(initialData || {});
  const [currentSection, setCurrentSection] = useState(0);
  const updateDiscovery = useUpdateDiscovery();
  const { toast } = useToast();
  const saveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (initialData) {
      setData(initialData);
    }
  }, [initialData]);

  /* Auto-save with debounce */
  const debouncedSave = (newData: Record<string, any>) => {
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(async () => {
      try {
        await updateDiscovery.mutateAsync({ id: strategyId, data: newData });
      } catch {
        /* silent */
      }
    }, 800);
  };

  const handleChange = (questionId: string, value: any) => {
    const next = { ...data, [questionId]: value };
    setData(next);
    debouncedSave(next);
  };

  const handleSave = async (showToast = true) => {
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    try {
      await updateDiscovery.mutateAsync({ id: strategyId, data });
      if (showToast) {
        toast({
          title: "Progress saved",
          description: "Your discovery questionnaire has been saved.",
        });
      }
    } catch {
      toast({
        title: "Failed to save",
        description: "Something went wrong.",
        variant: "destructive",
      });
    }
  };

  const handleNext = async () => {
    await handleSave(false);
    if (currentSection < SECTIONS.length - 1) {
      setCurrentSection((p) => p + 1);
    } else {
      if (onComplete) onComplete();
      toast({
        title: "Discovery Complete",
        description:
          "Your strategy generation will now be highly tailored. 🎯",
      });
    }
  };

  const handlePrev = async () => {
    await handleSave(false);
    setCurrentSection((p) => Math.max(0, p - 1));
  };

  /* Progress */
  const answeredCount = ALL_QUESTIONS.filter((q) => {
    const val = data[q.id];
    if (val == null) return false;
    if (typeof val === "string") return val.trim() !== "" && val !== "__other__";
    if (Array.isArray(val))
      return val.filter((v) => v && v !== "__other__").length > 0;
    return false;
  }).length;
  const progress = Math.round((answeredCount / ALL_QUESTIONS.length) * 100);

  const section = SECTIONS[currentSection];

  return (
    <Card className="discovery-wizard border-card-border bg-card p-0 shadow-lg overflow-hidden">
      {/* ---- Section stepper ---- */}
      <div className="discovery-stepper flex border-b border-border">
        {SECTIONS.map((s, i) => {
          const isCurrent = i === currentSection;
          const sectionAnswered = s.questions.filter((q) => {
            const val = data[q.id];
            if (val == null) return false;
            if (typeof val === "string")
              return val.trim() !== "" && val !== "__other__";
            if (Array.isArray(val))
              return val.filter((v) => v && v !== "__other__").length > 0;
            return false;
          }).length;
          const isCompleted = sectionAnswered > 0 && !isCurrent;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => {
                handleSave(false);
                setCurrentSection(i);
              }}
              className={`discovery-step flex-1 px-4 py-3.5 text-left transition-all relative ${
                isCurrent
                  ? "discovery-step--active"
                  : isCompleted
                    ? "discovery-step--completed"
                    : "discovery-step--pending"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`discovery-step-icon flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold ${
                    isCurrent
                      ? "bg-primary text-primary-foreground"
                      : isCompleted
                        ? "bg-primary/20 text-primary"
                        : "bg-muted text-muted-foreground"
                  }`}
                >
                  {isCompleted ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : (
                    i + 1
                  )}
                </span>
                <div className="min-w-0">
                  <div
                    className={`text-xs font-semibold truncate ${
                      isCurrent
                        ? "text-foreground"
                        : "text-muted-foreground"
                    }`}
                  >
                    {s.title}
                  </div>
                  <div className="text-[10px] text-muted-foreground/60">
                    {sectionAnswered}/{s.questions.length} answered
                  </div>
                </div>
              </div>
              {isCurrent && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
              )}
            </button>
          );
        })}
      </div>

      {/* ---- Progress bar ---- */}
      <div className="h-1 w-full bg-muted/30">
        <div
          className="h-full bg-gradient-to-r from-primary to-primary/70 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* ---- Section header ---- */}
      <div className="px-6 pt-5 pb-2">
        <div className="flex items-center gap-2 mb-1">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
            {section.icon}
          </div>
          <h2 className="text-lg font-semibold text-foreground">
            {section.title}
          </h2>
          <div className="ml-auto text-sm font-medium text-muted-foreground">
            {progress}% complete
          </div>
        </div>
        <p className="text-sm text-muted-foreground ml-9">{section.subtitle}</p>
      </div>

      {/* ---- Questions ---- */}
      <div className="px-6 py-4 space-y-6">
        {section.questions.map((q) => (
          <div key={q.id} className="discovery-question">
            <Label className="text-sm font-medium mb-1 block text-foreground">
              {q.title}
            </Label>
            <p className="text-xs text-muted-foreground mb-3">{q.desc}</p>

            {q.type === "text" && (
              <Input
                value={data[q.id] || ""}
                onChange={(e) => handleChange(q.id, e.target.value)}
                placeholder={q.placeholder}
                className="bg-background/50"
              />
            )}

            {q.type === "textarea" && (
              <Textarea
                value={data[q.id] || ""}
                onChange={(e) => handleChange(q.id, e.target.value)}
                placeholder={q.placeholder}
                rows={q.rows ?? 3}
                className="bg-background/50 resize-none"
              />
            )}

            {(q.type === "mcq" || q.type === "mcq_multi") && (
              <McqChips
                options={q.options ?? []}
                value={data[q.id] ?? (q.type === "mcq_multi" ? [] : "")}
                multi={q.type === "mcq_multi"}
                onChange={(val) => handleChange(q.id, val)}
              />
            )}
          </div>
        ))}
      </div>

      {/* ---- Navigation ---- */}
      <div className="px-6 py-4 border-t border-border flex items-center justify-between bg-muted/10">
        <Button
          variant="outline"
          onClick={handlePrev}
          disabled={currentSection === 0}
          className="gap-2"
        >
          <ChevronLeft className="w-4 h-4" />
          Previous
        </Button>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => handleSave()}
            disabled={updateDiscovery.isPending}
            className="gap-2"
          >
            <Save className="w-4 h-4" />
            Save Draft
          </Button>
          <Button
            onClick={handleNext}
            disabled={updateDiscovery.isPending}
            className="gap-2"
          >
            {currentSection === SECTIONS.length - 1 ? (
              <>
                <Sparkles className="w-4 h-4" />
                Finish & Generate
              </>
            ) : (
              <>
                Next
                <ChevronRight className="w-4 h-4" />
              </>
            )}
          </Button>
        </div>
      </div>
    </Card>
  );
}
