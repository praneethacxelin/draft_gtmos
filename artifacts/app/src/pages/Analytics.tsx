import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiFetch } from "@/lib/api";
import { useStrategies } from "@/hooks/useStrategies";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { useVerifyBulkEmails } from "@/hooks/useContacts";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import {
  Mail,
  MousePointerClick,
  MessageSquareReply,
  Send,
  AlertTriangle,
  BarChart3,
  ShieldCheck,
  Loader2,
  CheckCircle2,
  XCircle,
} from "lucide-react";

interface OutreachAnalytics {
  total_sent: number;
  total_opened: number;
  total_clicked: number;
  total_replied: number;
  total_bounced: number;
  open_rate: number;
  click_rate: number;
  reply_rate: number;
  bounce_rate: number;
  sequences: SequenceRow[];
  by_strategy: StrategyRow[];
}

interface SequenceRow {
  sequence_id: string;
  contact_id: string | null;
  contact_name: string;
  contact_email: string | null;
  email_verified: string | null;
  strategy_name: string;
  status: string;
  instantly_campaign_id: string | null;
  sent: number;
  opened: number;
  clicked: number;
  replied: number;
  bounced: number;
  open_rate: number;
  reply_rate: number;
}

interface StrategyRow {
  strategy_id: string;
  strategy_name: string;
  sent: number;
  opened: number;
  clicked: number;
  replied: number;
  bounced: number;
  open_rate: number;
  reply_rate: number;
}

function useOutreachAnalytics(strategyId?: string) {
  const qs = strategyId ? `?strategy_id=${strategyId}` : "";
  return useQuery<OutreachAnalytics>({
    queryKey: ["analytics", "outreach", strategyId ?? "all"],
    queryFn: () => apiFetch(`/api/analytics/outreach${qs}`),
    staleTime: 30_000,
  });
}

function MetricCard({
  label,
  value,
  sub,
  icon,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <Card
      className={`border-card-border p-4 ${accent ? "bg-primary/5" : "bg-card"}`}
    >
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          {label}
        </div>
        <div className="text-muted-foreground">{icon}</div>
      </div>
      <div className="mt-3 font-mono text-2xl tabular-nums text-foreground">
        {value}
      </div>
      {sub && (
        <div className="mt-0.5 text-[11px] text-muted-foreground">{sub}</div>
      )}
    </Card>
  );
}

function RateBar({ value }: { value: number }) {
  const capped = Math.min(value, 100);
  const color =
    value >= 30
      ? "bg-primary"
      : value >= 15
        ? "bg-amber-500"
        : "bg-muted-foreground/40";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${capped}%` }} />
      </div>
      <span className="font-mono text-xs tabular-nums">{value.toFixed(1)}%</span>
    </div>
  );
}

function VerificationBadge({ status }: { status: string | null }) {
  const map: Record<string, { label: string; cls: string }> = {
    valid: { label: "Valid", cls: "bg-primary/15 text-primary" },
    invalid: { label: "Invalid", cls: "bg-destructive/15 text-destructive" },
    catch_all: { label: "Catch-all", cls: "bg-amber-500/15 text-amber-500" },
    pending: { label: "Pending", cls: "bg-muted text-muted-foreground" },
  };
  if (!status) {
    return (
      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">
        Not verified
      </span>
    );
  }
  const m = map[status] ?? {
    label: status,
    cls: "bg-muted text-muted-foreground",
  };
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-widest ${m.cls}`}
    >
      {m.label}
    </span>
  );
}

export function Analytics() {
  const { data: strategies } = useStrategies();
  const { activeId } = useActiveStrategy();
  const [strategyFilter, setStrategyFilter] = useState<string>("all");

  const filterStratId =
    strategyFilter === "all" ? undefined : strategyFilter;
  const { data, isLoading } = useOutreachAnalytics(filterStratId);

  const verifyBulk = useVerifyBulkEmails();
  const [verifyResult, setVerifyResult] = useState<{
    verified: number;
    invalid: number;
    catch_all: number;
    total: number;
  } | null>(null);

  const bouncedRows = (data?.sequences ?? []).filter(
    (r) => r.bounced > 0 && r.contact_id && r.contact_email,
  );

  const handleVerifyBounced = () => {
    const ids = bouncedRows
      .map((r) => r.contact_id)
      .filter((id): id is string => !!id);
    if (ids.length === 0) return;
    verifyBulk.mutate(
      { contact_ids: ids, provider: "hunter" },
      {
        onSuccess: (res) => setVerifyResult(res),
      },
    );
  };

  return (
    <>
      <PageHeader
        eyebrow="Outreach analytics"
        title="Analytics"
        subtitle="Email engagement metrics pulled from Instantly campaigns and simulated sequences."
        actions={
          <Select
            value={strategyFilter}
            onValueChange={setStrategyFilter}
          >
            <SelectTrigger className="h-8 w-48 text-xs" data-testid="select-analytics-strategy">
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

      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-5">
            <MetricCard
              label="Emails sent"
              value={(data?.total_sent ?? 0).toLocaleString()}
              icon={<Send className="h-4 w-4" />}
            />
            <MetricCard
              label="Opened"
              value={(data?.total_opened ?? 0).toLocaleString()}
              sub={`${data?.open_rate ?? 0}% open rate`}
              icon={<Mail className="h-4 w-4" />}
              accent
            />
            <MetricCard
              label="Clicked"
              value={(data?.total_clicked ?? 0).toLocaleString()}
              sub={`${data?.click_rate ?? 0}% click rate`}
              icon={<MousePointerClick className="h-4 w-4" />}
            />
            <MetricCard
              label="Replied"
              value={(data?.total_replied ?? 0).toLocaleString()}
              sub={`${data?.reply_rate ?? 0}% reply rate`}
              icon={<MessageSquareReply className="h-4 w-4" />}
              accent
            />
            <MetricCard
              label="Bounced"
              value={(data?.total_bounced ?? 0).toLocaleString()}
              sub={`${data?.bounce_rate ?? 0}% bounce rate`}
              icon={<AlertTriangle className="h-4 w-4" />}
            />
          </div>

          {bouncedRows.length > 0 && (
            <div className="mt-6">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold">Bounced emails</h2>
                  <p className="text-xs text-muted-foreground">
                    Re-verify these addresses with Hunter.io or Instantly before
                    re-sending. Verification runs after delivery so credits are
                    only spent on addresses that actually bounced.
                  </p>
                </div>
                <Button
                  size="sm"
                  onClick={handleVerifyBounced}
                  disabled={verifyBulk.isPending}
                  data-testid="button-verify-bounced"
                >
                  {verifyBulk.isPending ? (
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <ShieldCheck className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  Verify {bouncedRows.length} bounced
                </Button>
              </div>

              {verifyBulk.isError && (
                <div className="mb-3 flex items-center gap-1.5 rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  <XCircle className="h-3.5 w-3.5" />
                  {(verifyBulk.error as Error)?.message ??
                    "Verification failed. Configure Hunter.io or Instantly in Settings."}
                </div>
              )}
              {verifyResult && (
                <div className="mb-3 flex flex-wrap items-center gap-3 rounded border border-card-border bg-card px-3 py-2 text-xs">
                  <span className="flex items-center gap-1 text-primary">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {verifyResult.verified} valid
                  </span>
                  <span className="flex items-center gap-1 text-destructive">
                    <XCircle className="h-3.5 w-3.5" />
                    {verifyResult.invalid} invalid
                  </span>
                  <span className="flex items-center gap-1 text-amber-500">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    {verifyResult.catch_all} catch-all
                  </span>
                  <span className="text-muted-foreground">
                    of {verifyResult.total} checked
                  </span>
                </div>
              )}

              <Card className="border-card-border bg-card overflow-hidden p-0">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40">
                    <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                      <th className="px-4 py-2">Contact</th>
                      <th className="px-4 py-2">Email</th>
                      <th className="px-4 py-2">Strategy</th>
                      <th className="px-4 py-2 text-right">Bounced</th>
                      <th className="px-4 py-2">Verification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {bouncedRows.map((row) => (
                      <tr key={row.sequence_id} className="hover:bg-muted/20">
                        <td className="px-4 py-2 font-medium">{row.contact_name}</td>
                        <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                          {row.contact_email ?? "—"}
                        </td>
                        <td className="px-4 py-2 text-xs text-muted-foreground">
                          {row.strategy_name || "—"}
                        </td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">
                          {row.bounced}
                        </td>
                        <td className="px-4 py-2">
                          <VerificationBadge status={row.email_verified} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            </div>
          )}

          {(data?.by_strategy?.length ?? 0) > 1 && (
            <div className="mt-6">
              <h2 className="mb-3 text-sm font-semibold">By strategy</h2>
              <Card className="border-card-border bg-card overflow-hidden p-0">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40">
                    <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                      <th className="px-4 py-2">Strategy</th>
                      <th className="px-4 py-2 text-right">Sent</th>
                      <th className="px-4 py-2 text-right">Opened</th>
                      <th className="px-4 py-2 text-right">Clicked</th>
                      <th className="px-4 py-2 text-right">Replied</th>
                      <th className="px-4 py-2">Open rate</th>
                      <th className="px-4 py-2">Reply rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data?.by_strategy.map((row) => (
                      <tr key={row.strategy_id} className="hover:bg-muted/20">
                        <td className="px-4 py-2 font-medium">{row.strategy_name}</td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">{row.sent}</td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">{row.opened}</td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">{row.clicked}</td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">{row.replied}</td>
                        <td className="px-4 py-2"><RateBar value={row.open_rate} /></td>
                        <td className="px-4 py-2"><RateBar value={row.reply_rate} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            </div>
          )}

          <div className="mt-6">
            <h2 className="mb-3 text-sm font-semibold">Per-contact sequences</h2>
            {(data?.sequences?.length ?? 0) === 0 ? (
              <Card className="border-card-border bg-card p-12 text-center">
                <BarChart3 className="mx-auto mb-3 h-8 w-8 text-muted-foreground/40" />
                <div className="text-sm font-medium text-foreground/70">No outreach data yet</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  Launch sequences from the Outreach page to start tracking engagement.
                  Live Instantly campaign data is synced hourly.
                </div>
              </Card>
            ) : (
              <Card className="border-card-border bg-card overflow-hidden p-0">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40">
                    <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                      <th className="px-4 py-2">Contact</th>
                      <th className="px-4 py-2">Email</th>
                      <th className="px-4 py-2">Status</th>
                      <th className="px-4 py-2 text-right">Sent</th>
                      <th className="px-4 py-2 text-right">Opened</th>
                      <th className="px-4 py-2 text-right">Clicked</th>
                      <th className="px-4 py-2 text-right">Replied</th>
                      <th className="px-4 py-2">Open rate</th>
                      <th className="px-4 py-2">Reply rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data?.sequences.map((row) => (
                      <tr key={row.sequence_id} className="hover:bg-muted/20">
                        <td className="px-4 py-2 font-medium">{row.contact_name}</td>
                        <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                          {row.contact_email ?? "—"}
                        </td>
                        <td className="px-4 py-2">
                          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">
                            {row.status}
                          </span>
                          {row.instantly_campaign_id && (
                            <span className="ml-1.5 rounded bg-orange-500/15 px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-orange-400">
                              Instantly
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">{row.sent}</td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">{row.opened}</td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">{row.clicked}</td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">{row.replied}</td>
                        <td className="px-4 py-2"><RateBar value={row.open_rate} /></td>
                        <td className="px-4 py-2"><RateBar value={row.reply_rate} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}
          </div>
        </>
      )}
    </>
  );
}
