import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Integration {
  name: string;
  display_name: string;
  description: string;
  key_label: string;
  is_connected: boolean;
  is_enabled: boolean;
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
