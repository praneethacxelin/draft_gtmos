import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import {
  useLearnings,
  useCreateLearning,
  useDeleteLearning,
  useCapturePersonaLearnings,
  type LearningCategory,
} from "@/hooks/useLearnings";
import {
  Lightbulb,
  Search,
  Plus,
  Trash2,
  Sparkles,
  Users,
  FlaskConical,
  MessageSquare,
  Clock,
  Layers,
  Radio,
  CircleDot,
} from "lucide-react";
import { toast } from "sonner";

const CATEGORY_META: Record<
  LearningCategory,
  { label: string; icon: typeof Lightbulb }
> = {
  persona: { label: "Persona", icon: Users },
  segment: { label: "Segment", icon: Layers },
  messaging: { label: "Messaging", icon: MessageSquare },
  timing: { label: "Timing", icon: Clock },
  experiment: { label: "Experiment", icon: FlaskConical },
  channel: { label: "Channel", icon: Radio },
  general: { label: "General", icon: CircleDot },
};

const CATEGORY_OPTIONS: { value: LearningCategory; label: string }[] = (
  Object.keys(CATEGORY_META) as LearningCategory[]
).map((k) => ({ value: k, label: CATEGORY_META[k].label }));

const CONFIDENCE_COLOR: Record<string, string> = {
  High: "text-green-500",
  Moderate: "text-yellow-500",
  Low: "text-muted-foreground",
};

export function Learnings() {
  const { active, activeId } = useActiveStrategy();
  const [scope, setScope] = useState<"all" | "strategy">("all");
  const [category, setCategory] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");

  const strategyId = scope === "strategy" ? activeId ?? undefined : undefined;
  const { data, isLoading } = useLearnings({
    strategyId,
    category: category === "all" ? undefined : category,
    q: query || undefined,
  });

  const createMut = useCreateLearning();
  const deleteMut = useDeleteLearning();
  const capturePersona = useCapturePersonaLearnings(activeId ?? undefined);

  const [newContent, setNewContent] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newCategory, setNewCategory] = useState<LearningCategory>("general");

  function submitNew() {
    const content = newContent.trim();
    if (!content) return;
    createMut.mutate(
      {
        content,
        title: newTitle.trim() || undefined,
        category: newCategory,
        strategy_id: scope === "strategy" ? activeId : undefined,
        source: "manual",
      },
      {
        onSuccess: () => {
          setNewContent("");
          setNewTitle("");
          toast.success("Learning saved");
        },
        onError: (e) => toast.error((e as Error).message),
      },
    );
  }

  function runQuery() {
    setQuery(search.trim());
  }

  const learnings = data ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Memory"
        title="Learnings"
        subtitle="The factory's durable memory — what experiments, personas, and outreach have taught us. Searchable by meaning across every product."
        actions={
          activeId ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                capturePersona.mutate(undefined, {
                  onSuccess: (r) =>
                    toast.success(
                      r.count > 0
                        ? `Captured ${r.count} persona learning${r.count === 1 ? "" : "s"}`
                        : "No persona data to capture yet",
                    ),
                  onError: (e) => toast.error((e as Error).message),
                })
              }
              disabled={capturePersona.isPending}
            >
              <Sparkles className="mr-1.5 h-3.5 w-3.5" />
              Capture persona insight
            </Button>
          ) : undefined
        }
      />

      {/* Add a learning */}
      <Card className="mb-6 border-card-border bg-card p-4">
        <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          <Plus className="h-3.5 w-3.5" />
          Record a learning
        </div>
        <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
          <div className="space-y-2">
            <Input
              placeholder="Title (optional)"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
            />
            <Textarea
              placeholder="What did we learn? e.g. 'Mid-market fintech replies 2x faster to ROI-led subject lines.'"
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              rows={3}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Select
              value={newCategory}
              onValueChange={(v) => setNewCategory(v as LearningCategory)}
            >
              <SelectTrigger className="w-full lg:w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORY_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              onClick={submitNew}
              disabled={!newContent.trim() || createMut.isPending}
            >
              Save learning
            </Button>
          </div>
        </div>
        {scope === "strategy" && active && (
          <div className="mt-2 text-[11px] text-muted-foreground">
            Will be tagged to {active.product_name}.
          </div>
        )}
      </Card>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Select value={scope} onValueChange={(v) => setScope(v as "all" | "strategy")}>
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All products</SelectItem>
            <SelectItem value="strategy" disabled={!activeId}>
              {active ? active.product_name : "Active product"}
            </SelectItem>
          </SelectContent>
        </Select>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {CATEGORY_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex flex-1 items-center gap-2">
          <Input
            placeholder="Search by meaning…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runQuery()}
            className="max-w-xs"
          />
          <Button variant="outline" size="sm" onClick={runQuery}>
            <Search className="mr-1.5 h-3.5 w-3.5" />
            Search
          </Button>
          {query && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearch("");
                setQuery("");
              }}
            >
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : learnings.length === 0 ? (
        <Card className="border-card-border bg-card p-10 text-center">
          <Lightbulb className="mx-auto mb-3 h-6 w-6 text-muted-foreground" />
          <div className="text-sm text-muted-foreground">
            {query
              ? "No learnings match your search."
              : "No learnings yet. Analyze an experiment batch or record one above."}
          </div>
        </Card>
      ) : (
        <div className="space-y-3">
          {learnings.map((l) => {
            const meta = CATEGORY_META[l.category] ?? CATEGORY_META.general;
            const Icon = meta.icon;
            return (
              <Card
                key={l.id}
                className="border-card-border bg-card p-4"
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded bg-primary/10 p-1.5 text-primary">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {l.title && (
                        <span className="font-medium text-foreground">
                          {l.title}
                        </span>
                      )}
                      <Badge variant="secondary" className="text-[10px]">
                        {meta.label}
                      </Badge>
                      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                        {l.source}
                      </span>
                      <span
                        className={`text-[10px] font-medium ${CONFIDENCE_COLOR[l.confidence] ?? ""}`}
                      >
                        {l.confidence}
                      </span>
                      {typeof l.similarity === "number" && (
                        <span className="text-[10px] font-mono text-muted-foreground">
                          {Math.round(l.similarity * 100)}% match
                        </span>
                      )}
                      <button
                        className="ml-auto text-muted-foreground transition-colors hover:text-red-500"
                        title="Delete"
                        onClick={() =>
                          deleteMut.mutate(l.id, {
                            onSuccess: () => toast.success("Deleted"),
                            onError: (e) => toast.error((e as Error).message),
                          })
                        }
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <p className="mt-1.5 text-sm text-foreground/90">
                      {l.content}
                    </p>
                    {l.tags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {l.tags.map((t, i) => (
                          <span
                            key={i}
                            className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
