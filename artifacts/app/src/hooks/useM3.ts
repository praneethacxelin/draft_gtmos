import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface EngagementEvent {
  id: string;
  channel: string;
  event_type: string;
  intent_contribution_score?: number;
  occurred_at?: string;
  account_id?: string;
  contact_id?: string;
}

export interface IntentRow {
  account_id: string;
  company_name?: string;
  score: number;
  classification: string;
  computed_at?: string;
}

export interface FeedbackEntry {
  id: string;
  source: string;
  sentiment: string;
  themes?: string[];
  raw_text?: string;
  captured_at?: string;
}

export interface AttributionRow {
  channel: string;
  count: number;
  value: number;
}

export interface QualSummary {
  sql: number;
  mql: number;
  nurture: number;
}

export interface LoopBackChange {
  field: string;
  current_value?: unknown;
  suggested_value?: unknown;
  reason?: string;
}

export interface LoopBackDelta {
  rationale?: string;
  changes?: LoopBackChange[];
  promote_personas?: string[];
  deprioritize_personas?: string[];
  summary?: string;
}

export interface LoopBack {
  id: string;
  delta?: LoopBackDelta | null;
  trigger_summary?: string;
  applied: boolean;
  applied_at?: string;
  created_at?: string;
}

export function useEngagementEvents(strategyId?: string) {
  return useQuery<EngagementEvent[]>({
    queryKey: ["m3", "events", strategyId],
    queryFn: () => apiFetch(`/api/m3/events?strategy_id=${strategyId}`),
    enabled: !!strategyId,
  });
}

export function useCreateEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      strategy_id: string;
      account_id?: string;
      contact_id?: string;
      channel: string;
      event_type: string;
    }) =>
      apiFetch("/api/m3/events", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["m3", "events"] });
      qc.invalidateQueries({ queryKey: ["m3", "intent"] });
    },
  });
}

export function useIntentScores(strategyId?: string) {
  return useQuery<IntentRow[]>({
    queryKey: ["m3", "intent", strategyId],
    queryFn: () => apiFetch(`/api/m3/intent?strategy_id=${strategyId}`),
    enabled: !!strategyId,
  });
}

export function useScoreIntent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (strategyId: string) =>
      apiFetch(`/api/m3/score-intent?strategy_id=${strategyId}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["m3", "intent"] });
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useFeedback(strategyId?: string) {
  return useQuery<FeedbackEntry[]>({
    queryKey: ["m3", "feedback", strategyId],
    queryFn: () => apiFetch(`/api/m3/feedback?strategy_id=${strategyId}`),
    enabled: !!strategyId,
  });
}

export function useCreateFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { strategy_id: string; source: string; raw_text: string }) =>
      apiFetch("/api/m3/feedback", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["m3", "feedback"] }),
  });
}

export function useAttribution(strategyId?: string) {
  return useQuery<AttributionRow[]>({
    queryKey: ["m3", "attribution", strategyId],
    queryFn: () => apiFetch(`/api/m3/attribution/summary?strategy_id=${strategyId}`),
    enabled: !!strategyId,
  });
}

export function useCreateAttribution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      strategy_id: string;
      source_channel: string;
      conversion_event: string;
      conversion_value?: number;
      touchpoint_type?: string;
    }) =>
      apiFetch("/api/m3/attribution", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["m3", "attribution"] }),
  });
}

export function useQualificationSummary(strategyId?: string) {
  return useQuery<QualSummary>({
    queryKey: ["m3", "qual-summary", strategyId],
    queryFn: () => apiFetch(`/api/m3/qualification-summary?strategy_id=${strategyId}`),
    enabled: !!strategyId,
  });
}

export function useQualifyContact() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (contactId: string) =>
      apiFetch(`/api/m3/qualify/${contactId}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["m3", "qual-summary"] }),
  });
}

export function useLoopBack(strategyId?: string) {
  return useQuery<LoopBack[]>({
    queryKey: ["m3", "loop-back", strategyId],
    queryFn: () => apiFetch(`/api/m3/loop-back?strategy_id=${strategyId}`),
    enabled: !!strategyId,
  });
}

export function useRunLoopBack() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (strategyId: string) =>
      apiFetch(`/api/m3/loop-back?strategy_id=${strategyId}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["m3", "loop-back"] }),
  });
}

export function useApplyLoopBack() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/m3/loop-back/${id}/apply`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["m3", "loop-back"] });
      qc.invalidateQueries({ queryKey: ["strategy"] });
    },
  });
}
