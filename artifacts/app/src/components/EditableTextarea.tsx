import { useState, useRef, useEffect } from "react";
import { Pencil } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Props {
  value: string;
  onSave: (v: string) => Promise<void> | void;
  className?: string;
  rows?: number;
  placeholder?: string;
  textClassName?: string;
}

export function EditableTextarea({
  value,
  onSave,
  className,
  rows = 3,
  placeholder,
  textClassName,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);

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
      <div className={cn("space-y-2", className)}>
        <Textarea
          ref={ref}
          value={draft}
          rows={rows}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setDraft(value);
              setEditing(false);
            }
          }}
          className="text-sm"
          disabled={saving}
        />
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={save}
            disabled={saving}
            className="h-7 text-xs"
          >
            {saving ? "Saving…" : "Save"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setDraft(value);
              setEditing(false);
            }}
            className="h-7 text-xs"
          >
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      onClick={() => setEditing(true)}
      className={cn(
        "group relative cursor-pointer rounded p-2 hover:bg-muted/30",
        className,
      )}
      title="Click to edit"
    >
      <span className={cn("text-sm leading-relaxed", textClassName)}>
        {value || (
          <span className="text-muted-foreground">{placeholder || "—"}</span>
        )}
      </span>
      <Pencil className="absolute right-2 top-2 h-3 w-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
    </div>
  );
}
