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

export type RoiVerdict =
  | "realistic"
  | "too_optimistic"
  | "too_conservative"
  | "insufficient_data";

export interface RoiCorrection {
  field: "expected_revenue" | "investment";
  from_usd?: number;
  to_usd?: number;
  reason?: string;
}

export interface RoiValidation extends WithProvenance {
  verdict?: RoiVerdict;
  headline?: string;
  expected_multiple?: number;
  benchmark?: {
    typical_roi_multiple_low?: number;
    typical_roi_multiple_high?: number;
    typical_payback_months?: number;
    avg_contract_value_usd?: number;
    typical_win_rate_pct?: number;
    typical_sales_cycle_months?: number;
    note?: string;
  };
  realistic_revenue_low_usd?: number;
  realistic_revenue_high_usd?: number;
  recommended_investment_usd?: number;
  calculator?: {
    accounts_reachable?: number;
    deals_expected?: number;
    projected_pipeline_usd?: number;
    projected_revenue_usd?: number;
    assumptions?: string[];
  };
  corrections?: RoiCorrection[];
  warnings?: string[];
  rationale?: string;
  inputs?: {
    investment_usd?: number;
    expected_revenue_usd?: number;
    timeframe_months?: number;
    market_segment?: string | null;
    notes?: string | null;
  };
  market_context?: {
    tam_usd?: number | null;
    sam_usd?: number | null;
    som_usd?: number | null;
    methodology?: string | null;
  };
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
  roi?: RoiValidation | null;
  discovery_data?: Record<string, unknown> | null;
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

export interface RoiValidateInput {
  investment_usd: number;
  expected_revenue_usd: number;
  timeframe_months?: number;
  market_segment?: string | null;
  notes?: string | null;
}

export function useValidateRoi() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: RoiValidateInput }) =>
      apiFetch<RoiValidation>(`/api/strategies/${id}/roi/validate`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: (_, { id }) =>
      qc.invalidateQueries({ queryKey: strategyKeys.detail(id) }),
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
    onSuccess: (result: unknown, id) => {
      qc.invalidateQueries({ queryKey: strategyKeys.patterns(id) });
      qc.invalidateQueries({ queryKey: ["contacts"] });
      import("sonner").then(({ toast }) => {
        const r = result as { patterns?: unknown[] } | null;
        const n = Array.isArray(r?.patterns) ? r!.patterns.length : null;
        toast.success(n != null ? `Pattern recognition complete — ${n} patterns found` : "Pattern recognition complete");
      }).catch(() => {});
    },
    onError: (err: Error) => {
      import("sonner").then(({ toast }) => toast.error(err.message)).catch(() => {});
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
    onSuccess: (result: unknown) => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
      import("sonner").then(({ toast }) => {
        const r = result as { accounts_added?: number; contacts_added?: number; cached?: boolean; message?: string } | null;
        if (r?.message) {
          toast.info(r.message);
        } else if (r) {
          toast.success(`Discovered ${r.contacts_added ?? 0} contacts across ${r.accounts_added ?? 0} accounts`);
        } else {
          toast.success("Lead discovery complete");
        }
      }).catch(() => {});
    },
    onError: (err: Error) => {
      import("sonner").then(({ toast }) => toast.error(err.message)).catch(() => {});
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
    onSuccess: (result: unknown) => {
      qc.invalidateQueries({ queryKey: ["signals"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
      import("sonner").then(({ toast }) => {
        const r = result as { signals_added?: number } | null;
        const n = r?.signals_added;
        toast.success(n != null ? `Signals scan complete — ${n} signals added` : "Signals scan complete");
      }).catch(() => {});
    },
    onError: (err: Error) => {
      import("sonner").then(({ toast }) => toast.error(err.message)).catch(() => {});
    },
  });
}

export function useScoreLeads() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => streamSse(`/api/strategies/${id}/score`),
    onSuccess: (result: unknown) => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
      import("sonner").then(({ toast }) => {
        const r = result as { scored?: number } | null;
        const n = r?.scored;
        toast.success(n != null ? `Scored ${n} leads` : "Lead scoring complete");
      }).catch(() => {});
    },
    onError: (err: Error) => {
      import("sonner").then(({ toast }) => toast.error(err.message)).catch(() => {});
    },
  });
}

export function useFetchContactEmails() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      streamSse(`/api/strategies/${id}/contacts/fetch-emails`),
    onSuccess: (result: unknown, id) => {
      qc.invalidateQueries({ queryKey: ["contacts", id] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
      import("sonner").then(({ toast }) => {
        const r = result as { updated?: number; message?: string; error?: string } | null;
        if (r?.error) {
          toast.error(r.error);
        } else {
          toast.success(r?.message ?? `Email fetch complete — ${r?.updated ?? 0} updated`);
        }
      }).catch(() => {});
    },
    onError: (err: Error) => {
      import("sonner").then(({ toast }) => toast.error(err.message)).catch(() => {});
    },
  });
}

export function useFetchContactPhones() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      streamSse(`/api/strategies/${id}/contacts/fetch-phones`),
    onSuccess: (result: unknown, id) => {
      qc.invalidateQueries({ queryKey: ["contacts", id] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
      import("sonner").then(({ toast }) => {
        const r = result as { updated?: number; message?: string; error?: string } | null;
        if (r?.error) {
          toast.error(r.error);
        } else {
          toast.success(r?.message ?? `Phone fetch complete — ${r?.updated ?? 0} updated`);
        }
      }).catch(() => {});
    },
    onError: (err: Error) => {
      import("sonner").then(({ toast }) => toast.error(err.message)).catch(() => {});
    },
  });
}

export function useUpdateStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Partial<
        Pick<
          Strategy,
          "product_name" | "description" | "target_market" | "pain_points_raw"
        >
      >;
    }) =>
      apiFetch<Strategy>(`/api/strategies/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: strategyKeys.detail(id) });
      qc.invalidateQueries({ queryKey: strategyKeys.list });
    },
  });
}

export type StrategySection = "icp" | "personas" | "problems" | "use-cases";

export function useUpdateStrategySection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      section,
      data,
    }: {
      id: string;
      section: StrategySection;
      data: object;
    }) =>
      apiFetch<Strategy>(`/api/strategies/${id}/${section}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: strategyKeys.detail(id) });
    },
  });
}
