import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiFetch } from "@/lib/api";
import { Search, Mail, Building2, UserCircle, CheckCircle2 } from "lucide-react";
import { useStrategies } from "@/hooks/useStrategies";
import { CRMContactPanel } from "@/components/CRMContactPanel";

export function CRM() {
  const [strategyFilter, setStrategyFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const { data: strategies } = useStrategies();
  const [selectedContact, setSelectedContact] = useState<any | null>(null);

  const qs = strategyFilter && strategyFilter !== "all" ? `?strategy_id=${strategyFilter}` : "";
  const { data: contacts, isLoading } = useQuery<any[]>({
    queryKey: ["contacts", "crm", strategyFilter],
    queryFn: () => apiFetch(`/api/crm/contacts${qs}`),
    staleTime: 30_000,
  });

  const filteredContacts = contacts?.filter((c) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      (c.full_name || "").toLowerCase().includes(q) ||
      (c.email || "").toLowerCase().includes(q) ||
      (c.account_name || "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="mx-auto w-full max-w-7xl p-6">
      <PageHeader
        title="CRM"
        subtitle="Manage and view all your leads across campaigns."
        actions={
          <Select value={strategyFilter} onValueChange={setStrategyFilter}>
            <SelectTrigger className="h-8 w-48 text-xs">
              <SelectValue placeholder="All strategies" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All strategies</SelectItem>
              {strategies?.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.product_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />

      <div className="mb-4 flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search leads by name, email, or company..."
            className="pl-9 h-9"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <Card className="border-card-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
              <th className="px-4 py-3 font-semibold">Contact</th>
              <th className="px-4 py-3 font-semibold">Company</th>
              <th className="px-4 py-3 font-semibold">Persona</th>
              <th className="px-4 py-3 font-semibold">Campaign</th>
              <th className="px-4 py-3 font-semibold text-center">Sent</th>
              <th className="px-4 py-3 font-semibold text-center">Replied</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              [...Array(5)].map((_, i) => (
                <tr key={i}>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-32" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-8 mx-auto" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-8 mx-auto" /></td>
                </tr>
              ))
            ) : filteredContacts?.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  No contacts found.
                </td>
              </tr>
            ) : (
              filteredContacts?.map((contact) => (
                <tr
                  key={contact.id}
                  className="hover:bg-muted/20 cursor-pointer transition-colors"
                  onClick={() => setSelectedContact(contact)}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium flex items-center gap-2">
                      <UserCircle className="h-4 w-4 text-muted-foreground" />
                      {contact.full_name || "Unknown"}
                    </div>
                    <div className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5 ml-6">
                      <Mail className="h-3 w-3" />
                      {contact.email || "—"}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-muted-foreground" />
                      {contact.account_name || "—"}
                    </div>
                    <div className="text-xs text-muted-foreground line-clamp-1 mt-0.5 ml-6">
                      {contact.title || "—"}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {contact.persona_type ? (
                      <span className="inline-flex items-center rounded-full border px-2 py-0.5 font-medium capitalize">
                        {contact.persona_type.replace("_", " ")}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-xs max-w-[150px] truncate">
                      {contact.campaign_name || "Unassigned"}
                    </div>
                    {contact.tier && (
                      <div className="text-[10px] text-primary bg-primary/10 inline-block px-1.5 rounded mt-1">
                        Tier {contact.tier}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {contact.sent > 0 ? (
                      <div className="flex items-center justify-center gap-1 text-green-500 font-medium">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        {contact.sent}
                      </div>
                    ) : (
                      <span className="text-muted-foreground/50">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {contact.replied > 0 ? (
                      <div className="flex items-center justify-center gap-1 text-blue-500 font-medium">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        {contact.replied}
                      </div>
                    ) : (
                      <span className="text-muted-foreground/50">—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>

      <CRMContactPanel
        contact={selectedContact}
        open={!!selectedContact}
        onOpenChange={(isOpen) => !isOpen && setSelectedContact(null)}
      />
    </div>
  );
}
