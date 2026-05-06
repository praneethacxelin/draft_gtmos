import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Signal {
  id: string;
  signal_type: string;
  source?: string;
  summary: string;
  strength_score: number;
  detected_at?: string;
  company_name?: string;
  is_demo: boolean;
}

export function useSignals(strategyId?: string) {
  return useQuery<Signal[]>({
    queryKey: ["signals", strategyId],
    queryFn: () => apiFetch(`/api/signals?strategy_id=${strategyId}`),
    enabled: !!strategyId,
  });
}
