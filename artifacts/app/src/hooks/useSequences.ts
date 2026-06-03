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
    onSuccess: (_, contactId) =>
      qc.invalidateQueries({ queryKey: ["sequence", "contact", contactId] }),
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
    mutationFn: ({ sequenceId, testEmail, schedule }: { sequenceId: string; testEmail?: string; schedule?: Record<string, any> }) =>
      streamSse(
        `/api/sequences/${sequenceId}/launch`,
        undefined,
        {
          ...(testEmail ? { test_email: testEmail } : {}),
          ...(schedule ? { schedule } : {})
        }
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sequence"] }),
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
