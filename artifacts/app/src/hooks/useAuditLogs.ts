import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface AuditEntry {
  id: string;
  occurred_at: string;
  event_type: string;
  service: string | null;
  strategy_id: string | null;
  strategy_name: string | null;
  http_method: string | null;
  endpoint_url: string | null;
  request_params: Record<string, unknown> | null;
  response_status: number | null;
  response_summary: Record<string, unknown> | null;
  latency_ms: number | null;
  curl_command: string | null;
  is_live: boolean;
  entity_type: string | null;
  entity_id: string | null;
  change_field: string | null;
  change_before: unknown;
  change_after: unknown;
  actor: string | null;
  summary: string | null;
}

export interface AuditLogsPayload {
  logs: AuditEntry[];
  total: number;
}

export interface AuditFilters {
  strategy_id?: string;
  service?: string;
  event_type?: string;
  from_ts?: string;
  to_ts?: string;
  limit?: number;
  offset?: number;
}

export function useAuditLogs(filters: AuditFilters = {}) {
  const params = new URLSearchParams();
  if (filters.strategy_id) params.set("strategy_id", filters.strategy_id);
  if (filters.service) params.set("service", filters.service);
  if (filters.event_type) params.set("event_type", filters.event_type);
  if (filters.from_ts) params.set("from_ts", filters.from_ts);
  if (filters.to_ts) params.set("to_ts", filters.to_ts);
  if (filters.limit) params.set("limit", String(filters.limit));
  if (filters.offset) params.set("offset", String(filters.offset));

  const qs = params.toString();
  return useQuery<AuditLogsPayload>({
    queryKey: ["audit-logs", filters],
    queryFn: () => apiFetch(`/api/audit-logs${qs ? `?${qs}` : ""}`),
    staleTime: 10_000,
  });
}
