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

export interface Sequence {
  id: string;
  status: string;
  channel_plan?: ChannelPlanStep[];
  provenance?: Provenance | null;
  deliverability_score?: number;
  deliverability_report?: DeliverabilityReport | null;
  instantly_campaign_id?: string;
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
    mutationFn: (contactId: string) =>
      apiFetch(`/api/sequences/generate/${contactId}`, { method: "POST" }),
    onSuccess: (_, contactId) => {
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
