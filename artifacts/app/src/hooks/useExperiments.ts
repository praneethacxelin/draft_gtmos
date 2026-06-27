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
  requested_leads?: number | null;
  sample_completeness?: number | null;
  sample_confidence?: number | null;
  adjusted_relevancy?: number | null;
  low_confidence?: boolean | null;
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

export interface LiveMetrics {
  contacted: number;
  opened: number;
  replied: number;
  interested: number;
  positive: number;
  reply_rate_pct: number;
  positive_rate_pct: number;
}

export type ExperimentTrustStatus =
  | "controlled"
  | "off_profile"
  | "inferred"
  | "unknown";

export interface ExperimentTrustViolation {
  facet: string;
  values: string[];
  allowed: string[];
  reason: string;
}

export interface ExperimentTrust {
  status: ExperimentTrustStatus;
  badges: string[];
  violations?: ExperimentTrustViolation[];
  missing_required?: string[];
  changed_facets?: string[];
  held_constant?: string[];
  contract_source?: string | null;
}

export interface Experiment {
  id: string;
  batch_id: string;
  strategy_id: string;
  idx: number;
  name?: string;
  hypothesis?: string;
  params: ExperimentParams;
  source: "ai" | "user";
  trust?: ExperimentTrust | null;
  status: ExperimentStatus;
  result_summary?: ExperimentResultSummary | null;
  leads: ExperimentLead[];
  relevancy?: ExperimentRelevancy | null;
  score?: number | null;
  error?: string | null;
  cohort_size?: number | null;
  live_launched_at?: string | null;
  live_metrics?: LiveMetrics | null;
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

export type LiveStatus = "drafted" | "running" | "completed" | null;

export interface LiveAnalysis {
  winner_experiment_id?: string | null;
  winner_name?: string | null;
  winner_metric?: string;
  ranking?: ({ experiment_id: string; name?: string } & LiveMetrics)[];
  any_positive?: boolean;
  recommendations?: string[];
  evaluated_at?: string;
}

export interface TargetingContract {
  strict: boolean;
  source?: string | null;
  locked: {
    locations: string[];
    industries: string[];
    employee_ranges: string[];
    titles: string[];
    technologies: string[];
    keywords: string[];
  };
  personas?: {
    economic_buyer?: string[];
    champion?: string[];
    blocker?: string[];
  };
  allowed_variation?: string[];
  notes?: string[];
}

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
  live_status?: LiveStatus;
  window_months?: number | null;
  window_started_at?: string | null;
  window_ends_at?: string | null;
  live_winner_experiment_id?: string | null;
  live_analysis?: LiveAnalysis | null;
  targeting_contract?: TargetingContract | null;
  created_at?: string;
  updated_at?: string;
}

export interface LiveMetricsResponse {
  batch_id: string;
  live_status?: LiveStatus;
  window_months?: number | null;
  window_started_at?: string | null;
  window_ends_at?: string | null;
  window_closed?: boolean;
  live_winner_experiment_id?: string | null;
  winner_metric?: string;
  variants: ({
    experiment_id: string;
    name?: string;
    idx?: number;
    cohort_size?: number;
    launched?: boolean;
  } & LiveMetrics)[];
  analysis?: LiveAnalysis | null;
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
    mutationFn: (data: {
      n: number;
      leads_per_experiment: number;
      hypothesis?: string;
      strict_discovery?: boolean;
      override_facets?: Record<string, string[]>;
    }) =>
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

/* ----------------------- Live (closed-loop) test ----------------------- */

export function useLiveMetrics(strategyId: string, batchId?: string, enabled = true) {
  return useQuery<LiveMetricsResponse>({
    queryKey: ["experiments", strategyId, batchId, "live"],
    queryFn: () =>
      apiFetch(`/api/strategies/${strategyId}/experiments/${batchId}/live`),
    enabled: !!strategyId && !!batchId && enabled,
    refetchInterval: 30000,
  });
}

export interface PromotionPlanVariant {
  experiment_id: string;
  name?: string;
  idx: number;
  is_winner: boolean;
  relevancy?: number | null;
  composite_score: number;
  available_leads: number;
  skipped: boolean;
  reason?: string | null;
  planned: number;
}

export interface PromotionPreview {
  batch_id: string;
  budget_per_variant: number;
  leads_per_experiment: number;
  total_to_promote: number;
  total_available: number;
  skipped_count: number;
  variants: PromotionPlanVariant[];
}

export function usePromotionPreview(
  strategyId: string,
  batchId: string,
  leadsPerVariant: number,
  enabled: boolean,
) {
  return useQuery<PromotionPreview>({
    queryKey: ["experiments", strategyId, batchId, "promote-preview", leadsPerVariant],
    queryFn: () =>
      apiFetch(
        `/api/strategies/${strategyId}/experiments/${batchId}/promote-preview?leads_per_variant=${leadsPerVariant}`,
      ),
    enabled: !!strategyId && !!batchId && enabled,
  });
}

export interface PromoteOptions {
  draftPerVariant?: number;
  autoSequence?: boolean;
  stepCount?: 4 | 5;
  dynamicTemplates?: boolean;
  runSignals?: boolean;
  scoreLeads?: boolean;
  recognizePatterns?: boolean;
  promoteTiers?: number[] | null;
}

export function usePromoteLive(strategyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      batchId,
      draftPerVariant,
      options,
    }: {
      batchId: string;
      draftPerVariant?: number;
      options?: PromoteOptions;
    }) => {
      const body: Record<string, unknown> = {};
      if (draftPerVariant != null) body.draft_per_variant = draftPerVariant;
      if (options) {
        if (options.autoSequence != null) body.auto_sequence = options.autoSequence;
        if (options.stepCount != null) body.step_count = options.stepCount;
        if (options.dynamicTemplates != null) body.dynamic_templates = options.dynamicTemplates;
        if (options.runSignals != null) body.run_signals = options.runSignals;
        if (options.scoreLeads != null) body.score_leads = options.scoreLeads;
        if (options.recognizePatterns != null)
          body.recognize_patterns = options.recognizePatterns;
        if (options.promoteTiers != null) body.promote_tiers = options.promoteTiers;
      }
      return apiFetch(
        `/api/strategies/${strategyId}/experiments/${batchId}/promote-live`,
        { method: "POST", body: JSON.stringify(body) },
      );
    },
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: experimentKeys.list(strategyId) }),
  });
}

export function useLaunchVariant(strategyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (experimentId: string) =>
      apiFetch(
        `/api/strategies/${strategyId}/experiments/experiments/${experimentId}/launch`,
        { method: "POST" },
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: experimentKeys.list(strategyId) }),
  });
}

export function useEvaluateLive(strategyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) =>
      apiFetch(`/api/strategies/${strategyId}/experiments/${batchId}/evaluate-live`, {
        method: "POST",
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: experimentKeys.list(strategyId) }),
  });
}

export function useSimulateWindow(strategyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) =>
      apiFetch(`/api/strategies/${strategyId}/experiments/${batchId}/simulate-window`, {
        method: "POST",
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: experimentKeys.list(strategyId) }),
  });
}
