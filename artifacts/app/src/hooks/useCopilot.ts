import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Play {
  contact_id: string;
  contact_name: string;
  title?: string;
  score: number;
  action: string;
  reason: string;
  recommended_copy?: string;
  urgency: "high" | "medium" | "low";
}

export function useCopilotFeed(strategyId?: string) {
  return useQuery<Play[]>({
    queryKey: ["copilot", strategyId],
    queryFn: () => apiFetch(`/api/copilot/feed?strategy_id=${strategyId}`),
    enabled: !!strategyId,
  });
}
