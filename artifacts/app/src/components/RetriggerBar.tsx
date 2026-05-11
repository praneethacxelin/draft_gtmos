import { X, Loader2, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface RetriggerAction {
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
  isPending?: boolean;
}

interface Props {
  actions: RetriggerAction[];
  onDismiss: () => void;
  message?: string;
}

export function RetriggerBar({ actions, onDismiss, message }: Props) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
      <RefreshCcw className="h-4 w-4 shrink-0 text-primary" />
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-foreground">
          {message ?? "Changes saved."}
        </span>
        <span className="text-sm text-muted-foreground">
          Retrigger downstream steps?
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {actions.map((a, i) => (
          <Button
            key={i}
            size="sm"
            variant="secondary"
            onClick={a.onClick}
            disabled={a.isPending}
            className="h-7 text-xs"
          >
            {a.isPending ? (
              <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
            ) : a.icon ? (
              <span className="mr-1.5 flex items-center">{a.icon}</span>
            ) : null}
            {a.label}
          </Button>
        ))}
        <button
          onClick={onDismiss}
          className="ml-1 rounded p-0.5 text-muted-foreground hover:text-foreground"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
