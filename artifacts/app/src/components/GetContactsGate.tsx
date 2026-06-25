import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Users } from "lucide-react";

export interface GetContactsParams {
  persona?: string;
  perAccount: number;
}

const PERSONA_OPTIONS = [
  { value: "any", label: "Any decision-maker" },
  { value: "champion", label: "Champion" },
  { value: "economic_buyer", label: "Economic buyer" },
  { value: "blocker", label: "Blocker" },
];

const COUNT_OPTIONS = [3, 5, 10, 15, 25, 50];

export function GetContactsGate({
  open,
  onOpenChange,
  selectedCount,
  pending,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  selectedCount: number;
  pending?: boolean;
  onConfirm: (params: GetContactsParams) => void;
}) {
  const [persona, setPersona] = useState<string>("any");
  const [perAccount, setPerAccount] = useState<string>("5");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Get contacts
          </DialogTitle>
          <DialogDescription>
            Pull people for the{" "}
            <span className="font-medium text-foreground">{selectedCount}</span>{" "}
            selected account{selectedCount === 1 ? "" : "s"}, matching the chosen
            persona. Emails stay hidden — reveal them later with Fetch emails so
            you only spend Apollo credits on contacts you keep.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
              Persona
            </label>
            <Select value={persona} onValueChange={setPersona}>
              <SelectTrigger className="h-9" data-testid="select-contact-persona">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PERSONA_OPTIONS.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
              Contacts per account
            </label>
            <Select value={perAccount} onValueChange={setPerAccount}>
              <SelectTrigger className="h-9" data-testid="select-contact-count">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {COUNT_OPTIONS.map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} per account
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={pending || selectedCount === 0}
            onClick={() =>
              onConfirm({
                persona: persona === "any" ? undefined : persona,
                perAccount: Number(perAccount),
              })
            }
            data-testid="button-confirm-get-contacts"
          >
            {pending ? "Pulling…" : `Pull contacts (${selectedCount} acct)`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
