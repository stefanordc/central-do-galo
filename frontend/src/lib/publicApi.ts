const PUBLIC_API_BASE =
  "https://lhrpsquyzehevxuogxar.supabase.co/functions/v1/central-public-api";

const PUBLIC_API_KEY =
  "sb_publishable_nl8JhRCQKlI2o1DEEmHwKQ_5IsNoIYZ";

export function publicApiFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  headers.set("apikey", PUBLIC_API_KEY);

  return fetch(`${PUBLIC_API_BASE}${path}`, {
    ...init,
    headers,
  });
}
