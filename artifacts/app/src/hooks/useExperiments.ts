import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { Provenance } from "@/hooks/useStrategies";

/* ------------------------------------------------------------------ */
/*  Types                                                            */
/* ------------------------------------------------------------------ */

export interface ExperimentParams {
  titles?: string[];
  seniorities?: string[];
  locations?: string[];
  industries?: string[];
  employee_ranges?: string[];
  technologies?: string[];
  revenue_ranges?: string[];
  keywords?: string[];
}

export interface ExperimentLead {
  name?: string;
  title?: string;
  seniority?: string;
  company?: string;
  domain?: string;
  industry?: string;
  employee_count?: number;
  revenue_range?: string;
  location?: string;
  hq_location?: string;
  linkedin_url?: string;
}

export interface ExperimentRelevancy {
  relevancy_score?: number | null;
  relevant_count?: number;
  irrelevant_count?: number;
  off_target_industries?: string[];
  irrelevant_examples?: { company?: string; industry?: string; reason?: string }[];
  summary?: string;
}

export interface ExperimentResultSummary {
  lead_count?: number;
  winning_tier?: string | null;
  relaxed?: boolean;
  industry_spread?: Record<string, number>;
  location_spread?: Record<string, number>;
  requested_leads?: number;
  _provenance?: Provenance;
}

export type ExperimentStatus = "draft" | "running" | "done" | "failed";

export interface Experiment {
  id: string;
  batch_id: string;
  strategy_id: string;
  idx: number;
  name?: string;
  hypothesis?: string;
  params: ExperimentParams;
  source: "ai" | "user";
  status: ExperimentStatus;
  result_summary?: ExperimentResultSummary | null;
  leads: ExperimentLead[];
  relevancy?: ExperimentRelevancy | null;
  score?: number | null;
  error?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface BatchAnalysis {
  best_experiment_id?: string;
  why_best?: string;
  ranking?: { experiment_id: string; rank: number; verdict: string }[];
  winning_parameters_insight?: string;
  recommendations?: string[];
  _provenance?: Provenance;
}

export type BatchStatus = "draft" | "seeded" | "running" | "analyzed";

export interface ExperimentBatch {
  id: string;
  strategy_id: string;
  name?: string;
  n_experiments: number;
  leads_per_experiment: number;
  status: BatchStatus;
  hypothesis?: string;
  best_experiment_id?: string | null;
  analysis?: BatchAnalysis | null;
  experiments?: Experiment[];
  created_at?: string;
  updated_at?: string;
}

/* ------------------------------------------------------------------ */
/*  Keys                                                             */
/* ------------------------------------------------------------------ */

export const experimentKeys = {
  list: (strategyId: string) => ["experiments", strategyId] as const,
};

/* ------------------------------------------------------------------ */
/*  Queries / mutations                                              */
/* ------------------------------------------------------------------ */

export function useExperimentBatches(strategyId?: string) {
  return useQuery<ExperimentBatch[]>({
    queryKey: strategyId ? experimentKeys.list(strategyId) : ["experiments", "none"],
    queryFn: () => apiFetch(`/api/strategies/${strategyId}/experiments`),
    enabled: !!strategyId,
  });
}

export function useCreateExperimentBatch(strategyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { n: number; leads_per_experiment: number; hypothesis?: string }) =>
      apiFetch<ExperimentBatch>(`/api/strategies/${strategyId}/experiments`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: experimentKeys.list(strategyId) }),
  });
}

export function useDeleteExperimentBatch(strategyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) =>
      apiFetch(`/api/strategies/${strategyId}/experiments/${batchId}`, {
        method: "DELETE",
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: experimentKeys.list(strategyId) }),
  });
}

export function useUpdateExperiment(strategyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      experimentId,
      data,
    }: {
      experimentId: string;
      data: { name?: string; hypothesis?: string; params?: ExperimentParams };
    }) =>
      apiFetch<Experiment>(
        `/api/strategies/${strategyId}/experiments/experiments/${experimentId}`,
        { method: "PATCH", body: JSON.stringify(data) },
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: experimentKeys.list(strategyId) }),
  });
}

export function useRunExperiment(strategyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (experimentId: string) =>
      apiFetch<Experiment>(
        `/api/strategies/${strategyId}/experiments/experiments/${experimentId}/run`,
        { method: "POST" },
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: experimentKeys.list(strategyId) }),
  });
}

export function useRunBatch(strategyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) =>
      apiFetch<ExperimentBatch>(
        `/api/strategies/${strategyId}/experiments/${batchId}/run`,
        { method: "POST" },
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: experimentKeys.list(strategyId) }),
  });
}

export function useAnalyzeBatch(strategyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) =>
      apiFetch<ExperimentBatch>(
        `/api/strategies/${strategyId}/experiments/${batchId}/analyze`,
        { method: "POST" },
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: experimentKeys.list(strategyId) }),
  });
}
