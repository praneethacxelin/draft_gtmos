import { useEffect, useState, type KeyboardEvent } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { X, Plus, Loader2, Building2, Sparkles, Info } from "lucide-react";
import {
  useFilterPreview,
  type ApolloFacets,
} from "@/hooks/useStrategies";

type FacetKey = keyof ApolloFacets;

const FREE_TEXT_FIELDS: {
  key: FacetKey;
  label: string;
  placeholder: string;
  hint?: string;
}[] = [
  { key: "titles", label: "Job titles", placeholder: "e.g. Head of Customer Support" },
  { key: "locations", label: "Locations (countries)", placeholder: "e.g. United States" },
  { key: "industries", label: "Industries", placeholder: "e.g. Software", hint: "Free-text — Apollo may ignore non-taxonomy values." },
  { key: "employee_ranges", label: "Company size", placeholder: "e.g. 51,200", hint: "Apollo 'min,max' ranges." },
  { key: "technologies", label: "Technologies", placeholder: "e.g. Zendesk", hint: "Tools the buyer already uses." },
  { key: "keywords", label: "Keywords", placeholder: "e.g. ticketing", hint: "Narrows hard — only set if needed." },
];

const EMPTY_FACETS: ApolloFacets = {
  titles: [],
  seniorities: [],
  locations: [],
  industries: [],
  employee_ranges: [],
  technologies: [],
  keywords: [],
};

function TagInput({
  values,
  onChange,
  placeholder,
}: {
  values: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState("");

  function add() {
    const v = draft.trim();
    if (!v) return;
    if (!values.includes(v)) onChange([...values, v]);
    setDraft("");
  }

  function handleKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add();
    } else if (e.key === "Backspace" && !draft && values.length) {
      onChange(values.slice(0, -1));
    }
  }

  return (
    <div className="rounded-md border border-input bg-background p-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        {values.map((v) => (
          <span
            key={v}
            className="inline-flex items-center gap-1 rounded bg-muted px-2 py-0.5 text-xs"
          >
            {v}
            <button
              type="button"
              onClick={() => onChange(values.filter((x) => x !== v))}
              className="text-muted-foreground hover:text-foreground"
              aria-label={`Remove ${v}`}
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        <span className="flex flex-1 items-center gap-1">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKey}
            onBlur={add}
            placeholder={values.length ? "" : placeholder}
            className="h-7 min-w-[8rem] flex-1 border-0 px-1 text-xs shadow-none focus-visible:ring-0"
          />
          {draft.trim() && (
            <button
              type="button"
              onClick={add}
              className="text-muted-foreground hover:text-foreground"
              aria-label="Add"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          )}
        </span>
      </div>
    </div>
  );
}

/**
 * Pre-execution gate: shows the exact Apollo parameters that will be sent and
 * lets the user edit every facet before discovery runs. Confirming returns the
 * edited facets, which the caller passes through as `override_filters`.
 */
export function ApolloFilterGate({
  open,
  onOpenChange,
  strategyId,
  pending,
  confirmLabel,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  strategyId: string;
  pending: boolean;
  confirmLabel: string;
  onConfirm: (facets: ApolloFacets) => void;
}) {
  const { data, isLoading, isError, error } = useFilterPreview(strategyId, open);
  const [facets, setFacets] = useState<ApolloFacets>(EMPTY_FACETS);
  const [initializedFor, setInitializedFor] = useState<string | null>(null);

  // Seed the editable state once the design loads (re-seed per strategy).
  useEffect(() => {
    if (data?.facets && initializedFor !== strategyId) {
      setFacets({ ...EMPTY_FACETS, ...data.facets });
      setInitializedFor(strategyId);
    }
  }, [data, strategyId, initializedFor]);

  // Reset the "initialized" guard whenever the dialog is closed so reopening
  // re-seeds from a fresh design.
  useEffect(() => {
    if (!open) setInitializedFor(null);
  }, [open]);

  const seniorityOptions = data?.seniority_options ?? [];

  function setField(key: FacetKey, next: string[]) {
    setFacets((f) => ({ ...f, [key]: next }));
  }

  function toggleSeniority(s: string) {
    setFacets((f) => ({
      ...f,
      seniorities: f.seniorities.includes(s)
        ? f.seniorities.filter((x) => x !== s)
        : [...f.seniorities, s],
    }));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-primary" />
            Review Apollo parameters
          </DialogTitle>
          <DialogDescription>
            These are the exact filters that will be sent to Apollo to find your
            accounts. Edit any facet before running — your changes are used
            verbatim.
          </DialogDescription>
        </DialogHeader>

        {isLoading && (
          <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Designing filters from your ICP &amp; discovery answers…
          </div>
        )}

        {isError && (
          <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {(error as Error)?.message || "Failed to design filters."}
          </div>
        )}

        {!isLoading && !isError && (
          <div className="space-y-4 py-1">
            {data && !data.apollo_key_present && (
              <div className="flex items-start gap-2 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-600 dark:text-amber-400">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                No Apollo API key configured — discovery will return synthetic
                demo accounts using these filters as guidance.
              </div>
            )}
            {data?.ai_designed && (
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5" />
                AI-designed from your ICP, personas &amp; discovery answers.
              </p>
            )}

            {FREE_TEXT_FIELDS.slice(0, 1).map((f) => (
              <div key={f.key} className="space-y-1.5">
                <Label className="text-xs">{f.label}</Label>
                <TagInput
                  values={facets[f.key]}
                  onChange={(next) => setField(f.key, next)}
                  placeholder={f.placeholder}
                />
                {f.hint && (
                  <p className="text-[11px] text-muted-foreground">{f.hint}</p>
                )}
              </div>
            ))}

            <div className="space-y-1.5">
              <Label className="text-xs">Seniorities</Label>
              <div className="flex flex-wrap gap-1.5">
                {seniorityOptions.map((s) => {
                  const active = facets.seniorities.includes(s);
                  return (
                    <button
                      key={s}
                      type="button"
                      onClick={() => toggleSeniority(s)}
                      className={
                        "rounded-full border px-2.5 py-1 text-xs capitalize transition-colors " +
                        (active
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-input text-muted-foreground hover:bg-muted")
                      }
                    >
                      {s.replace("_", " ")}
                    </button>
                  );
                })}
              </div>
            </div>

            {FREE_TEXT_FIELDS.slice(1).map((f) => (
              <div key={f.key} className="space-y-1.5">
                <Label className="text-xs">{f.label}</Label>
                <TagInput
                  values={facets[f.key]}
                  onChange={(next) => setField(f.key, next)}
                  placeholder={f.placeholder}
                />
                {f.hint && (
                  <p className="text-[11px] text-muted-foreground">{f.hint}</p>
                )}
              </div>
            ))}
          </div>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={pending}>
            Cancel
          </Button>
          <Button
            onClick={() => onConfirm(facets)}
            disabled={pending || isLoading || isError}
          >
            {pending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Running…
              </>
            ) : (
              confirmLabel
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
