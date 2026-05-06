import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface DashboardSummary {
  strategies: number;
  ready_strategies: number;
  total_contacts: number;
  tier_1_contacts: number;
  active_sequences: number;
  top_intent_account?: { company_name: string; score: number; classification: string } | null;
}

export interface ActivityItem {
  type: string;
  title: string;
  detail: string;
  at?: string;
}

export function useDashboardSummary() {
  return useQuery<DashboardSummary>({
    queryKey: ["dashboard", "summary"],
    queryFn: () => apiFetch("/api/dashboard/summary"),
    refetchInterval: 15000,
  });
}

export function useDashboardActivity() {
  return useQuery<ActivityItem[]>({
    queryKey: ["dashboard", "activity"],
    queryFn: () => apiFetch("/api/dashboard/activity"),
  });
}
