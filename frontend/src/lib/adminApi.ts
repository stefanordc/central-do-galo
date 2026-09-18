const ADMIN_API_BASE =
  "https://lhrpsquyzehevxuogxar.supabase.co/functions/v1/central-admin-api";

export function adminApiFetch(path: string, init: RequestInit = {}) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return fetch(`${ADMIN_API_BASE}${normalized}`, {
    ...init,
    cache: init.cache ?? "no-store",
  });
}
