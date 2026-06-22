import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export type LearningCategory =
  | "persona"
  | "segment"
  | "messaging"
  | "timing"
  | "experiment"
  | "channel"
  | "general";

export type LearningSource =
  | "experiment"
  | "persona"
  | "outreach"
  | "roi"
  | "manual";

export interface Learning {
  id: string;
  strategy_id: string | null;
  category: LearningCategory;
  title: string | null;
  content: string;
  source: LearningSource;
  source_ref: string | null;
  metrics: Record<string, unknown>;
  tags: string[];
  confidence: "High" | "Moderate" | "Low";
  embedded: boolean;
  created_at: string | null;
  updated_at: string | null;
  similarity?: number;
}

export interface LearningCreateInput {
  content: string;
  category?: LearningCategory;
  title?: string;
  strategy_id?: string | null;
  source?: LearningSource;
  source_ref?: string | null;
  metrics?: Record<string, unknown>;
  tags?: string[];
  confidence?: "High" | "Moderate" | "Low";
}

export const learningKeys = {
  all: ["learnings"] as const,
  list: (params: {
    strategyId?: string;
    category?: string;
    source?: string;
    q?: string;
  }) => ["learnings", params] as const,
};

function buildQuery(params: {
  strategyId?: string;
  category?: string;
  source?: string;
  q?: string;
}): string {
  const sp = new URLSearchParams();
  if (params.strategyId) sp.set("strategy_id", params.strategyId);
  if (params.category) sp.set("category", params.category);
  if (params.source) sp.set("source", params.source);
  if (params.q) sp.set("q", params.q);
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export function useLearnings(params: {
  strategyId?: string;
  category?: string;
  source?: string;
  q?: string;
} = {}) {
  return useQuery({
    queryKey: learningKeys.list(params),
    queryFn: () =>
      apiFetch<Learning[]>(`/api/learnings${buildQuery(params)}`),
  });
}

export function useCreateLearning() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: LearningCreateInput) =>
      apiFetch<Learning>("/api/learnings", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: learningKeys.all });
    },
  });
}

export function useDeleteLearning() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<{ ok: boolean }>(`/api/learnings/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: learningKeys.all });
    },
  });
}

export interface CaptureResult {
  captured: Learning[];
  count: number;
}

export function useCapturePersonaLearnings(strategyId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<CaptureResult>(
        `/api/strategies/${strategyId}/learnings/capture-persona`,
        { method: "POST" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: learningKeys.all });
    },
  });
}

export function useCaptureExperimentLearnings(strategyId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) =>
      apiFetch<CaptureResult>(
        `/api/strategies/${strategyId}/learnings/capture-experiment/${batchId}`,
        { method: "POST" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: learningKeys.all });
    },
  });
}
