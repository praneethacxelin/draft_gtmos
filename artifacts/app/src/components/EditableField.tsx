import { useState, useRef, useEffect } from "react";
import { Pencil, Check, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface Props {
  value: string;
  onSave: (v: string) => Promise<void> | void;
  className?: string;
  inputClassName?: string;
  placeholder?: string;
  displayClassName?: string;
}

export function EditableField({
  value,
  onSave,
  className,
  inputClassName,
  placeholder,
  displayClassName,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) ref.current?.focus();
  }, [editing]);

  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  async function save() {
    const trimmed = draft.trim();
    if (trimmed === value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onSave(trimmed);
    } finally {
      setSaving(false);
      setEditing(false);
    }
  }

  if (editing) {
    return (
      <span className={cn("inline-flex items-center gap-1", className)}>
        <Input
          ref={ref}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              save();
            }
            if (e.key === "Escape") {
              setDraft(value);
              setEditing(false);
            }
          }}
          onBlur={save}
          className={cn("h-7 px-2 text-sm", inputClassName)}
          disabled={saving}
        />
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={save}
          className="shrink-0 rounded p-0.5 text-primary hover:opacity-70"
          disabled={saving}
        >
          <Check className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            setDraft(value);
            setEditing(false);
          }}
          className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </span>
    );
  }

  return (
    <span
      onClick={() => setEditing(true)}
      className={cn(
        "group inline-flex cursor-pointer items-center gap-1 rounded px-1 hover:bg-muted/40",
        className,
      )}
      title="Click to edit"
    >
      <span className={displayClassName}>{value || placeholder || "—"}</span>
      <Pencil className="h-3 w-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
    </span>
  );
}
