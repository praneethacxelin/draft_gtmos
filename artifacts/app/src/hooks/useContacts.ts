import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Contact {
  id: string;
  full_name: string;
  title?: string;
  email?: string;
  email_verified?: string;
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
  source?: string;
  source_ref?: string;
  account_id: string;
  company_name?: string;
  industry?: string;
  domain?: string;
  location?: string;
  pain_point?: string;
  recent_signal?: string;
  icebreaker?: string;
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
      apiFetch<Contact>(`/api/contacts/${id}/reveal?type=email`, {
        method: "POST",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useRevealContactPhone() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<Contact>(`/api/contacts/${id}/reveal?type=phone`, {
        method: "POST",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useVerifyContactEmail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, provider }: { id: string; provider?: string }) =>
      apiFetch<Contact>(
        `/api/contacts/${id}/verify${provider ? `?provider=${provider}` : ""}`,
        {
          method: "POST",
        },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useVerifyBulkEmails() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      contact_ids,
      provider,
    }: {
      contact_ids: string[];
      provider?: string;
    }) =>
      apiFetch<{ verified: number; invalid: number; catch_all: number; total: number }>(`/api/contacts/verify-bulk`, {
        method: "POST",
        body: JSON.stringify({ contact_ids, provider }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}
