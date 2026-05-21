import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Contact {
  id: string;
  full_name: string;
  title?: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  seniority?: string;
  department?: string;
  persona_type?: string;
  icp_fit_score: number;
  signal_score: number;
  engagement_score: number;
  total_score: number;
  tier?: number;
  is_demo: boolean;
  account_id: string;
  company_name?: string;
  industry?: string;
  domain?: string;
}

export function useContacts(strategyId?: string, tier?: number) {
  return useQuery<Contact[]>({
    queryKey: ["contacts", strategyId, tier ?? "all"],
    queryFn: () => {
      const tierParam = tier ? `&tier=${tier}` : "";
      return apiFetch(`/api/contacts?strategy_id=${strategyId}${tierParam}`);
    },
    enabled: !!strategyId,
  });
}

export function useContact(id?: string) {
  return useQuery<Contact>({
    queryKey: ["contact", id],
    queryFn: () => apiFetch(`/api/contacts/${id}`),
    enabled: !!id,
  });
}

export function useUpdateContact() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Partial<
        Pick<
          Contact,
          "full_name" | "title" | "email" | "phone" | "persona_type" | "icp_fit_score" | "seniority"
        >
      >;
    }) =>
      apiFetch<Contact>(`/api/contacts/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useRevealContactEmail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<Contact>(`/api/contacts/${id}/reveal`, {
        method: "POST",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}
