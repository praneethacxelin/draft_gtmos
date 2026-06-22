import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Account {
  id: string;
  company_name: string;
  domain?: string;
  industry?: string;
  employee_count?: number;
  revenue_range?: string;
  location?: string;
  founded_year?: number;
  tier?: number;
  tech_stack?: string[];
  signal_count: number;
  contact_count: number;
  intent_score?: number;
  intent_classification?: string;
  source?: string;
}

export function useAccounts(strategyId?: string) {
  return useQuery<Account[]>({
    queryKey: ["accounts", strategyId],
    queryFn: () => apiFetch(`/api/accounts?strategy_id=${strategyId}`),
    enabled: !!strategyId,
  });
}

export function usePrioritizedAccounts(strategyId?: string) {
  return useQuery<{ tier_1: Account[]; tier_2: Account[]; tier_3: Account[] }>({
    queryKey: ["accounts", "prioritized", strategyId],
    queryFn: () => apiFetch(`/api/accounts/prioritized?strategy_id=${strategyId}`),
    enabled: !!strategyId,
  });
}
