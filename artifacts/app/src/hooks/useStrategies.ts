import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch, streamSse } from "@/lib/api";

export interface IcpSegment {
  name: string;
  fit_score: number;
  rationale?: string;
}

export interface Icp extends WithProvenance {
  industries?: string[];
  employee_size_range?: string;
  revenue_range?: string;
  geographies?: string[];
  tech_stack_signals?: string[];
  segments?: IcpSegment[];
  scoring_rules?: { signal: string; weight: number }[];
}

export interface Persona {
  title?: string;
  goals?: string[];
  frustrations?: string[];
  success_metrics?: string[];
  communication_style?: string;
  objections?: string[];
}

export interface PersonaMatrix extends WithProvenance {
  champion?: Persona;
  economic_buyer?: Persona;
  blocker?: Persona;
  influence_edges?: { from: string; to: string; label: string }[];
}

export interface ProblemRow {
  persona: string;
  pain: string;
  trigger: string;
  product_angle: string;
  urgency: "low" | "medium" | "high";
}

export interface NaicsSegment {
  naics_code: string;
  name: string;
  sub_vertical?: string;
  opportunity_score?: number;
  est_company_count?: number;
  rationale?: string;
}

export interface StakeholderNode {
  id: string;
  label: string;
  role?: string;
  tier: "champion" | "blocker" | "economic_buyer" | "influencer";
  influence?: number;
}

export interface StakeholderEdge {
  from: string;
  to: string;
  label?: string;
}

export interface StakeholderMap extends WithProvenance {
  nodes?: StakeholderNode[];
  edges?: StakeholderEdge[];
}

export interface UseCase {
  title: string;
  vertical?: string;
  persona?: string;
  scenario?: string;
  value_prop?: string;
  proof_point_placeholder?: string;
}

export interface MoneyBlock {
  value_usd?: number;
  label?: string;
}

export type ProvenanceSource =
  | "ai_generated"
  | "serpapi"
  | "apollo"
  | "instantly"
  | "clay"
  | "computed"
  | "legacy";

export interface Provenance {
  source: ProvenanceSource;
  logic: string;
  steps: string[];
  counts: Record<string, number>;
  generated_at: string;
  model?: string;
  extra?: Record<string, unknown>;
}

export interface WithProvenance {
  _provenance?: Provenance;
}

export interface TamSamSom extends WithProvenance {
  tam?: MoneyBlock;
  sam?: MoneyBlock;
  som?: MoneyBlock;
  methodology?: string;
  confidence?: "low" | "medium" | "high";
  uses_live_data?: boolean;
}

export interface Strategy {
  id: string;
  product_name: string;
  description: string;
  target_market?: string | null;
  pain_points_raw?: string | null;
  status: "draft" | "generating" | "ready";
  icp?: Icp | null;
  personas?: PersonaMatrix | null;
  problems?: ({ problems?: ProblemRow[] } & WithProvenance) | null;
  naics?: ({ segments?: NaicsSegment[] } & WithProvenance) | null;
  stakeholder_map?: StakeholderMap | null;
  use_cases?: ({ use_cases?: UseCase[] } & WithProvenance) | null;
  tam_sam_som?: TamSamSom | null;
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

function withLimit(path: string, limit?: number) {
  return limit ? `${path}?limit=${limit}` : path;
}

export function useMarketSizing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: string | { id: string; limit?: number }) => {
      const { id, limit } = typeof vars === "string" ? { id: vars, limit: undefined } : vars;
      return streamSse(withLimit(`/api/strategies/${id}/market-sizing`, limit));
    },
    onSuccess: (_, vars) => {
      const id = typeof vars === "string" ? vars : vars.id;
      qc.invalidateQueries({ queryKey: strategyKeys.detail(id) });
    },
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
    mutationFn: (id: string) => streamSse(`/api/strategies/${id}/competitors/run`),
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
    mutationFn: (id: string) => streamSse(`/api/strategies/${id}/patterns/run`),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: strategyKeys.patterns(id) });
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useLeadSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: string | { id: string; limit?: number }) => {
      const { id, limit } = typeof vars === "string" ? { id: vars, limit: undefined } : vars;
      return streamSse(withLimit(`/api/strategies/${id}/leads/search`, limit));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useRunSignals() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: string | { id: string; limit?: number }) => {
      const { id, limit } = typeof vars === "string" ? { id: vars, limit: undefined } : vars;
      return streamSse(withLimit(`/api/strategies/${id}/signals/run`, limit));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["signals"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useScoreLeads() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => streamSse(`/api/strategies/${id}/score`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}
