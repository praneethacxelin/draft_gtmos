import { useState } from "react";
import { Pencil } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Props {
  items: string[];
  onSave: (items: string[]) => Promise<void> | void;
  placeholder?: string;
  chipClassName?: string;
}

export function EditableList({ items, onSave, placeholder, chipClassName }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(items.join("\n"));
  const [saving, setSaving] = useState(false);

  function open() {
    setDraft(items.join("\n"));
    setEditing(true);
  }

  async function save() {
    const newItems = draft
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    setSaving(true);
    try {
      await onSave(newItems);
    } finally {
      setSaving(false);
      setEditing(false);
    }
  }

  if (editing) {
    return (
      <div className="space-y-2">
        <Textarea
          value={draft}
          rows={Math.max(3, items.length + 1)}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setDraft(items.join("\n"));
              setEditing(false);
            }
          }}
          placeholder="One item per line"
          className="font-mono text-xs"
          disabled={saving}
          autoFocus
        />
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={save} disabled={saving} className="h-7 text-xs">
            {saving ? "Saving…" : "Save"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setDraft(items.join("\n"));
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
      className="group cursor-pointer"
      onClick={open}
      title="Click to edit"
    >
      {items.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1">
          {items.map((item, i) => (
            <span
              key={i}
              className={cn(
                "rounded bg-muted px-1.5 py-0.5 text-xs text-foreground/80",
                chipClassName,
              )}
            >
              {item}
            </span>
          ))}
          <Pencil className="ml-0.5 h-3 w-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
      ) : (
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <span>{placeholder || "Click to add items"}</span>
          <Pencil className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
      )}
    </div>
  );
}
