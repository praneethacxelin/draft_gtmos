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

export interface SignalMover {
  contact_id: string;
  contact_name: string;
  title?: string;
  company?: string;
  before: number;
  after: number;
  delta: number;
}

export interface RecentSignal {
  signal_type: string;
  summary: string;
  company?: string;
  strength?: number;
  source?: string;
  detected_at?: string;
}

export interface SignalPulse {
  strategy_id?: string;
  strategy_name?: string;
  has_serpapi: boolean;
  last_scanned?: string | null;
  new_signals: number;
  is_demo?: boolean;
  top_movers: SignalMover[];
  recent_signals: RecentSignal[];
  message?: string | null;
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

export function useSignalPulse(strategyId?: string) {
  return useQuery<SignalPulse>({
    queryKey: ["dashboard", "signal-pulse", strategyId ?? "auto"],
    queryFn: () =>
      apiFetch(
        `/api/dashboard/signal-pulse${strategyId ? `?strategy_id=${strategyId}` : ""}`,
      ),
    refetchInterval: 60000,
  });
}

