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
    revenue_target_usd?: number | null;
    average_deal_size_usd?: number | null;
    conversion_rate?: number;
    lead_acquisition_cost?: number;
    outreach_cost?: number;
    gtm_engineer_capacity?: number;
    current_gtm_engineers?: number;
    time_urgency?: string;
    campaign_count?: number;
    sales_cycle_months?: number;
    execution_start_month?: number;
  };
  market_context?: {
    tam_usd?: number | null;
    sam_usd?: number | null;
    som_usd?: number | null;
    methodology?: string | null;
  };
  gtm_plan?: GtmPlan | null;
}

export type CampaignMode = "parallel" | "sequential" | "hybrid";

export type RevenueAssessment =
  | "Conservative"
  | "Realistic"
  | "Aggressive"
  | "Unrealistic";

export interface GtmPlanCampaign {
  name: string;
  prospects: number;
  engineers: number;
  closures: number;
  throughput_prospects?: number;
  utilization_pct?: number | null;
  bottleneck?: boolean;
}

export type ConfidenceLevel = "High" | "Moderate" | "Low";

export interface RevenuePhase {
  phase: number;
  label: string;
  month_range: string;
  calendar_range: string;
  quarter: string;
  base_target_usd: number;
  carried_in_usd: number;
  phase_target_usd: number;
  effective_target_usd?: number;
  required_closures: number;
  required_prospects: number;
  phase_capacity_prospects: number;
  season_factor: number;
  season_notes?: string[];
  projected_attainment_pct: number;
  projected_revenue_usd: number;
  carry_forward_usd: number;
  confidence: ConfidenceLevel;
}

export interface RevenuePlan {
  sales_cycle_months: number;
  execution_start_month: number;
  execution_start_label: string;
  phase_count: number;
  annual_target_usd: number;
  projected_total_usd: number;
  projected_coverage_pct: number;
  final_shortfall_usd: number;
  overall_confidence: ConfidenceLevel;
  seasonality_impact?: string | null;
  phases: RevenuePhase[];
}

export interface GtmPlan {
  inputs?: {
    revenue_target_usd?: number;
    average_deal_size_usd?: number;
    conversion_rate?: number;
    lead_acquisition_cost?: number;
    outreach_cost?: number;
    serp_api_cost?: number;
    ai_token_cost?: number;
    gtm_engineer_capacity?: number;
    current_gtm_engineers?: number;
    time_horizon_months?: number;
    time_urgency?: string;
    campaign_count?: number;
    email_accounts?: number;
    email_account_type?: string;
    sales_cycle_months?: number;
    execution_start_month?: number;
  };
  required_closures?: number;
  required_prospects?: number;
  costs?: {
    lead_acquisition_cost_usd?: number;
    outreach_cost_usd?: number;
    serp_api_cost_usd?: number;
    ai_token_cost_usd?: number;
    total_gtm_cost_usd?: number;
    budget_sufficient?: boolean;
    planned_investment_usd?: number | null;
  };
  capacity?: {
    working_days?: number;
    capacity_per_engineer?: number;
    available_capacity?: number;
    required_capacity?: number;
    utilization_pct?: number | null;
    capacity_gap?: number;
    sufficient?: boolean;
    current_engineers?: number;
    recommended_engineers?: number;
    additional_engineers?: number;
    message?: string;
  };
  campaign_plan?: {
    mode?: CampaignMode;
    campaign_count?: number;
    reasoning?: string;
    campaigns?: GtmPlanCampaign[];
    waves?: string[][];
    bottlenecks?: string[];
    available_engineers?: number;
  };
  revenue_plan?: RevenuePlan | null;
  email_capacity?: {
    email_accounts?: number;
    email_account_type?: string;
    per_account_per_day?: number;
    daily_capacity?: number;
    monthly_capacity?: number;
    total_capacity?: number;
    experiment_window_capacity?: number;
    required_prospects?: number;
    sufficient?: boolean;
    recommended_accounts?: number;
    additional_accounts?: number;
    message?: string | null;
  };
  experiment_plan?: {
    window_months?: number;
    n_experiments?: number;
    leads_per_experiment?: number;
    total_experiment_leads?: number;
    window_send_capacity?: number;
    capacity_limited?: boolean;
    hypotheses?: {
      idx?: number;
      persona?: string;
      segment?: string;
      angle?: string | null;
      label?: string;
      leads?: number;
    }[];
    rationale?: string;
  };
  reconciliation?: {
    target_usd?: number;
    forward_revenue_usd?: number;
    reaches_target?: boolean;
    realistic_low_usd?: number | null;
    realistic_high_usd?: number | null;
    alignment?: "above_realistic" | "below_realistic" | "within_realistic" | "unknown";
    prospects_for_realistic_low?: number | null;
    prospects_for_realistic_high?: number | null;
  };
  revenue_assessment?: RevenueAssessment;
  strategic_guidance?: string[];
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
  revenue_target_usd?: number | null;
  average_deal_size_usd?: number | null;
  conversion_rate?: number;
  lead_acquisition_cost?: number;
  outreach_cost?: number;
  gtm_engineer_capacity?: number;
  current_gtm_engineers?: number;
  time_urgency?: string;
  campaign_count?: number;
  sales_cycle_months?: number;
  execution_start_month?: number;
  serp_api_cost?: number;
  ai_token_cost?: number;
  email_accounts?: number;
  email_account_type?: string;
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

export interface PersonaFunnelStage {
  stage: string;
  count: number;
}

export interface PersonaScore {
  persona_type: string;
  label: string;
  contacts: number;
  score: number;
  grade: string;
  confidence: "High" | "Moderate" | "Low";
  basis: "funnel" | "contact_scores";
  metrics: {
    sent: number;
    opened: number;
    clicked: number;
    replied: number;
    bounced: number;
    open_rate_pct: number;
    reply_rate_pct: number;
    qualified: number;
    sql: number;
    conversions: number;
    won: number;
    conversion_value_usd: number;
    avg_response_hours: number | null;
    avg_funnel_depth: number;
  };
  components: {
    response: number;
    depth: number;
    conversion: number;
    speed: number;
  };
  funnel: PersonaFunnelStage[];
}

export interface PersonaIntelligence {
  strategy_id: string;
  persona_count: number;
  total_contacts: number;
  data_basis?: "funnel" | "contact_scores";
  personas: PersonaScore[];
  top_performer?: { persona_type: string; label: string; score: number } | null;
  lowest_performer?: { persona_type: string; label: string; score: number } | null;
  recommendations: string[];
}

export function usePersonaIntelligence(id?: string) {
  return useQuery<PersonaIntelligence>({
    queryKey: id ? [...strategyKeys.detail(id), "persona-intelligence"] : ["persona-intel", "none"],
    queryFn: () => apiFetch(`/api/strategies/${id}/persona-intelligence`),
    enabled: !!id,
  });
}

export interface PersonaAllocationRow {
  persona_type: string;
  label: string;
  rank: number;
  score: number;
  grade: string;
  confidence: "High" | "Moderate" | "Low";
  weight_pct: number;
  prospect_count: number;
  reply_rate_pct: number | null;
  avg_funnel_depth: number | null;
}

export interface PersonaAllocation {
  strategy_id: string;
  data_basis?: "funnel" | "contact_scores";
  weights_input: number[];
  total_prospects: number | null;
  allocated_personas: number;
  allocations: PersonaAllocationRow[];
  deprioritized_personas: { persona_type: string; label: string; score: number }[];
  notes: string[];
}

export function usePersonaAllocation(id?: string, totalProspects?: number | null) {
  const qp =
    totalProspects != null && totalProspects > 0 ? `?total_prospects=${Math.round(totalProspects)}` : "";
  return useQuery<PersonaAllocation>({
    queryKey: id
      ? [...strategyKeys.detail(id), "persona-allocation", totalProspects ?? 0]
      : ["persona-alloc", "none"],
    queryFn: () => apiFetch(`/api/strategies/${id}/persona-allocation${qp}`),
    enabled: !!id,
  });
}

export interface CampaignPlanPersonaSplit {
  persona_type: string;
  label: string;
  weight_pct: number;
  prospect_count: number;
}

export interface CampaignPlanPhase {
  phase: number;
  label: string;
  calendar_range: string;
  quarter: string;
  revenue_target_usd: number;
  required_closures: number;
  prospect_count: number;
  prospect_share_pct: number;
  baseline_prospects: number;
  persona_split: CampaignPlanPersonaSplit[];
  season_factor: number | null;
  confidence: "High" | "Moderate" | "Low" | null;
}

export interface CampaignPlan {
  ready: boolean;
  gate: "ready" | "roi_pending" | "experiments_pending" | "missing_strategy";
  reason?: string;
  strategy_id?: string;
  source_batch_id?: string;
  winning_experiment_id?: string;
  winning_experiment_name?: string | null;
  winning_facets?: Record<string, string[] | string>;
  winning_parameters_insight?: string | null;
  kickoff_month?: number;
  kickoff_label?: string;
  experiment_window_months?: number;
  total_prospects?: number;
  frontload_decay?: number;
  frontload_first_two_pct?: number;
  phase_count?: number;
  annual_target_usd?: number;
  overall_confidence?: "High" | "Moderate" | "Low";
  phases?: CampaignPlanPhase[];
  notes?: string[];
}

export function useCampaignPlan(id?: string) {
  return useQuery<CampaignPlan>({
    queryKey: id ? [...strategyKeys.detail(id), "campaign-plan"] : ["campaign-plan", "none"],
    queryFn: () => apiFetch(`/api/strategies/${id}/campaign-plan`),
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

export interface ApolloFacets {
  titles: string[];
  seniorities: string[];
  locations: string[];
  industries: string[];
  employee_ranges: string[];
  technologies: string[];
  keywords: string[];
}

export interface FilterPreview {
  facets: ApolloFacets;
  seniority_options: string[];
  ai_designed: boolean;
  apollo_key_present: boolean;
}

/**
 * Designs (but does not run) the Apollo facets for the params gate. Lazy:
 * pass `enabled` (e.g. dialog-open state) so the LLM design only runs when the
 * user actually opens the preview. Cached for the session to avoid re-charging.
 */
export function useFilterPreview(id?: string, enabled = false) {
  return useQuery<FilterPreview>({
    queryKey: id ? [...strategyKeys.detail(id), "filter-preview"] : ["filter-preview", "none"],
    queryFn: () => apiFetch(`/api/strategies/${id}/leads/filter-preview`),
    enabled: !!id && enabled,
    staleTime: Infinity,
    gcTime: 5 * 60 * 1000,
    retry: false,
  });
}

export function useDiscoverAccounts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      limit,
      facets,
    }: {
      id: string;
      limit?: number;
      facets?: Partial<ApolloFacets>;
    }) =>
      streamSse(
        withLimit(`/api/strategies/${id}/accounts/discover`, limit),
        undefined,
        facets,
      ),
    onSuccess: (result: unknown) => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      import("sonner")
        .then(({ toast }) => {
          const r = result as
            | { accounts_added?: number; is_demo?: boolean; message?: string }
            | null;
          if (r?.message) {
            toast.info(r.message);
          } else if (r) {
            const demo = r.is_demo ? " (demo)" : "";
            toast.success(`Discovered ${r.accounts_added ?? 0} accounts${demo}`);
          } else {
            toast.success("Account discovery complete");
          }
        })
        .catch(() => {});
    },
    onError: (err: Error) => {
      import("sonner").then(({ toast }) => toast.error(err.message)).catch(() => {});
    },
  });
}

export function useGetContacts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      limit,
      facets,
    }: {
      id: string;
      limit?: number;
      facets?: Partial<ApolloFacets>;
    }) =>
      streamSse(
        withLimit(`/api/strategies/${id}/leads/contacts`, limit),
        undefined,
        facets,
      ),
    onSuccess: (result: unknown) => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
      import("sonner")
        .then(({ toast }) => {
          const r = result as
            | { accounts_added?: number; contacts_added?: number; cached?: boolean; message?: string }
            | null;
          if (r?.message) {
            toast.info(r.message);
          } else if (r) {
            toast.success(
              `Added ${r.contacts_added ?? 0} contacts across ${r.accounts_added ?? 0} accounts`,
            );
          } else {
            toast.success("Contacts pulled");
          }
        })
        .catch(() => {});
    },
    onError: (err: Error) => {
      import("sonner").then(({ toast }) => toast.error(err.message)).catch(() => {});
    },
  });
}

export function useDiscoverExperimentLeads() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: string | { id: string; limit?: number }) => {
      const { id, limit } = typeof vars === "string" ? { id: vars, limit: undefined } : vars;
      return streamSse(withLimit(`/api/strategies/${id}/leads/discover-experiments`, limit));
    },
    onSuccess: (result: unknown) => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["contacts"] });
      import("sonner").then(({ toast }) => {
        const r = result as
          | { ready?: boolean; reason?: string; contacts_added?: number; accounts_added?: number; message?: string }
          | null;
        if (r && r.ready === false) {
          toast.info(r.reason ?? "Experiment discovery is not ready yet");
        } else if (r?.message) {
          toast.info(r.message);
        } else if (r) {
          toast.success(
            `Experiment discovery added ${r.contacts_added ?? 0} contacts across ${r.accounts_added ?? 0} accounts`,
          );
        } else {
          toast.success("Experiment discovery complete");
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
