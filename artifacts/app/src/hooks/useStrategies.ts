import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Strategy {
  id: string;
  product_name: string;
  description: string;
  target_market?: string | null;
  pain_points_raw?: string | null;
  status: "draft" | "generating" | "ready";
  icp?: any;
  personas?: any;
  problems?: any;
  naics?: any;
  stakeholder_map?: any;
  use_cases?: any;
  tam_sam_som?: any;
  created_at?: string;
}

export interface Competitor {
  id: string;
  name: string;
  website?: string;
  positioning?: string;
  features?: string[];
  pricing_info?: string;
  weaknesses?: string[];
  g2_rating?: number;
}

export interface Pattern {
  id: string;
  pattern_name: string;
  signal_combination?: string[];
  conversion_rate: number;
}

export const strategyKeys = {
  list: ["strategies"] as const,
  detail: (id: string) => ["strategy", id] as const,
  competitors: (id: string) => ["strategy", id, "competitors"] as const,
  patterns: (id: string) => ["strategy", id, "patterns"] as const,
};

export function useStrategies() {
  return useQuery<Strategy[]>({
    queryKey: strategyKeys.list,
    queryFn: () => apiFetch("/api/strategies"),
  });
}

export function useStrategy(id?: string) {
  return useQuery<Strategy>({
    queryKey: id ? strategyKeys.detail(id) : ["strategy", "none"],
    queryFn: () => apiFetch(`/api/strategies/${id}`),
    enabled: !!id,
  });
}

export function useCreateStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      product_name: string;
      description: string;
      target_market?: string;
      pain_points_raw?: string;
    }) =>
      apiFetch<Strategy>("/api/strategies", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: strategyKeys.list }),
  });
}

export function useDeleteStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/strategies/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: strategyKeys.list }),
  });
}

export function useMarketSizing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/strategies/${id}/market-sizing`, { method: "POST" }),
    onSuccess: (_, id) =>
      qc.invalidateQueries({ queryKey: strategyKeys.detail(id) }),
  });
}

export function useCompetitors(id?: string) {
  return useQuery<Competitor[]>({
    queryKey: id ? strategyKeys.competitors(id) : ["competitors", "none"],
    queryFn: () => apiFetch(`/api/strategies/${id}/competitors`),
    enabled: !!id,
  });
}

export function useRunCompetitors() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/strategies/${id}/competitors/run`, { method: "POST" }),
    onSuccess: (_, id) =>
      qc.invalidateQueries({ queryKey: strategyKeys.competitors(id) }),
  });
}

export function usePatterns(id?: string) {
  return useQuery<Pattern[]>({
    queryKey: id ? strategyKeys.patterns(id) : ["patterns", "none"],
    queryFn: () => apiFetch(`/api/strategies/${id}/patterns`),
    enabled: !!id,
  });
}

export function useRunPatterns() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/strategies/${id}/patterns/run`, { method: "POST" }),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: strategyKeys.patterns(id) });
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useLeadSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/strategies/${id}/leads/search`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useRunSignals() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/strategies/${id}/signals/run`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["signals"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useScoreLeads() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/strategies/${id}/score`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}
