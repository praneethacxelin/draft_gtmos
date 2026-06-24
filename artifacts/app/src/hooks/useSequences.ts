import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch, streamSse } from "@/lib/api";

export interface SequenceStep {
  id: string;
  step_number: number;
  channel: "email" | "linkedin" | "call";
  subject?: string;
  body?: string;
  wait_days: number;
  send_at?: string;
  sent_at?: string;
  status: string;
}

export interface ChannelPlanStep {
  step: number;
  channel: "email" | "linkedin" | "call";
  wait_days: number;
}

export interface DeliverabilityReport {
  score: number;
  flagged_phrases?: string[];
  link_count?: number;
  avg_length?: number;
  notes?: string;
}

import type { Provenance } from "./useStrategies";

export interface CampaignStats {
  sent: number;
  opened: number;
  clicked: number;
  replied: number;
  bounced: number;
  opportunities: number;
  opportunity_value: number;
  open_rate: number;
  click_rate: number;
  reply_rate: number;
  email_list?: string[];
}

export interface InstantlyCampaignInfo {
  id: string;
  instantly_campaign_id: string;
  status: string;
  analytics?: CampaignStats | null;
  synced_at?: string | null;
}

export interface Sequence {
  id: string;
  status: string;
  channel_plan?: ChannelPlanStep[];
  provenance?: Provenance | null;
  deliverability_score?: number;
  deliverability_report?: DeliverabilityReport | null;
  instantly_campaign_id?: string;
  campaigns?: InstantlyCampaignInfo[];
  steps: SequenceStep[];
}

export function useSequenceByContact(contactId?: string) {
  return useQuery<Sequence | null>({
    queryKey: ["sequence", "contact", contactId],
    queryFn: () => apiFetch(`/api/sequences/by-contact/${contactId}`),
    enabled: !!contactId,
  });
}

export function useGenerateSequence() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ contactId, stepCount }: { contactId: string; stepCount?: number }) => {
      const q = stepCount ? `?step_count=${stepCount}` : "";
      return apiFetch(`/api/sequences/generate/${contactId}${q}`, { method: "POST" });
    },
    onSuccess: (_, { contactId }) => {
      // Invalidate the specific contact sequence AND the broader query tree
      // so any components watching sequences all get fresh data.
      qc.invalidateQueries({ queryKey: ["sequence", "contact", contactId], refetchType: "all" });
      qc.invalidateQueries({ queryKey: ["sequence"], refetchType: "all" });
    },
  });
}

export function useDeliverabilityCheck() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sequenceId: string) =>
      apiFetch(`/api/sequences/${sequenceId}/deliverability-check`, {
        method: "POST",
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["sequence"] }),
  });
}

export function useLaunchSequence() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      sequenceId,
      testEmail,
      schedule,
      is_test,
    }: {
      sequenceId: string;
      testEmail?: string;
      schedule?: Record<string, any>;
      is_test?: boolean;
    }) =>
      streamSse(
        `/api/sequences/${sequenceId}/launch`,
        undefined,
        {
          ...(testEmail ? { test_email: testEmail } : {}),
          ...(schedule ? { schedule } : {}),
          is_test: is_test ?? false,
        }
      ),
    onSuccess: (data: any) => {
      qc.invalidateQueries({ queryKey: ["sequence"] });
      import("sonner").then(({ toast }) => {
        if (data?.instantly_pushed) {
          toast.success(
            `Campaign launched via Instantly${data.is_test ? " (Test)" : ""}`,
            { description: `Recipient: ${data.lead_email ?? "—"}` }
          );
        } else {
          toast.success("Sequence launched (simulated)", {
            description: "No Instantly key configured — engagement timeline simulated.",
          });
        }
      }).catch(() => {});
    },
    onError: (err: Error) => {
      import("sonner").then(({ toast }) => {
        toast.error("Launch failed", { description: err.message });
      }).catch(() => {});
    },
  });
}

export function useUpdateSequenceStep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Partial<Pick<SequenceStep, "subject" | "body" | "channel" | "wait_days" | "send_at">>;
    }) =>
      apiFetch(`/api/sequences/steps/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sequence"] });
    },
  });
}

export interface SendingAccount {
  email: string;
  first_name: string;
  last_name: string;
  provider_code: number;
  status: number;
  warmup_status: number;
  health_score: number;
  sent_count: number;
  received_count: number;
  landed_inbox: number;
}

export function useSendingAccounts() {
  return useQuery<SendingAccount[]>({
    queryKey: ["sendingAccounts"],
    queryFn: () => apiFetch("/api/sequences/sending-accounts"),
  });
}

export function useConnectSendingAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      email: string;
      first_name: string;
      last_name: string;
      provider_code: number;
      app_password: string;
      imap_host?: string;
      imap_port?: number;
      smtp_host?: string;
      smtp_port?: number;
    }) =>
      apiFetch("/api/sequences/sending-accounts/connect", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sendingAccounts"] });
    },
  });
}

export function useToggleWarmup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { email: string; enable: boolean }) =>
      apiFetch("/api/sequences/sending-accounts/warmup/toggle", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sendingAccounts"] });
    },
  });
}

export function useDisconnectSendingAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (email: string) =>
      apiFetch(`/api/sequences/sending-accounts/${email}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sendingAccounts"] });
    },
  });
}

export interface Reply {
  id: string;
  subject: string;
  body: string;
  from_address_name?: string;
  from_address_email?: string;
  to_address_email?: string;
  ue_type: number; // 1=sent, 2=received/reply
  timestamp_created: string;
}

export function useContactReplies(contactId?: string) {
  return useQuery<Reply[]>({
    queryKey: ["sequence", "contact", contactId, "replies"],
    queryFn: () => apiFetch(`/api/sequences/by-contact/${contactId}/replies`),
    enabled: !!contactId,
    // Poll every 10 seconds to keep replies fresh and live!
    refetchInterval: 10000,
  });
}

export function usePauseCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (campaignId: string) =>
      apiFetch(`/api/sequences/campaigns/${campaignId}/pause`, {
        method: "POST",
      }),
    onSuccess: (_, campaignId) => {
      qc.invalidateQueries({ queryKey: ["sequence"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useResumeCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (campaignId: string) =>
      apiFetch(`/api/sequences/campaigns/${campaignId}/resume`, {
        method: "POST",
      }),
    onSuccess: (_, campaignId) => {
      qc.invalidateQueries({ queryKey: ["sequence"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

