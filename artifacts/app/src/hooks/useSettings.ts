import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Integration {
  name: string;
  display_name: string;
  description: string;
  key_label: string;
  is_connected: boolean;
  is_enabled: boolean;
  key_last_four?: string | null;
  last_tested_at?: string | null;
  test_status?: string | null;
  test_message?: string | null;
}

export function useIntegrations() {
  return useQuery<Integration[]>({
    queryKey: ["integrations"],
    queryFn: () => apiFetch("/api/settings/integrations"),
  });
}

export function useUpdateIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      name,
      api_key,
      is_enabled,
    }: {
      name: string;
      api_key?: string | null;
      is_enabled: boolean;
    }) =>
      apiFetch(`/api/settings/integrations/${name}`, {
        method: "PUT",
        body: JSON.stringify({ api_key, is_enabled }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["integrations"] }),
  });
}

export interface FetchLimitsPayload {
  limits: { leads_per_run: number; signals_per_account: number; market_sizing_results: number };
  maximums: { leads_per_run: number; signals_per_account: number; market_sizing_results: number };
  defaults: { leads_per_run: number; signals_per_account: number; market_sizing_results: number };
}

export function useFetchLimits() {
  return useQuery<FetchLimitsPayload>({
    queryKey: ["fetch-limits"],
    queryFn: () => apiFetch("/api/settings/fetch-limits"),
  });
}

export function useUpdateFetchLimits() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<FetchLimitsPayload["limits"]>) =>
      apiFetch<FetchLimitsPayload>("/api/settings/fetch-limits", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fetch-limits"] }),
  });
}

export function useTestIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      apiFetch<{ ok: boolean; message: string }>(
        `/api/settings/integrations/${name}/test`,
        { method: "POST" },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["integrations"] }),
  });
}
