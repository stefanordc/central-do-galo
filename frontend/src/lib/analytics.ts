import { publicApiFetch } from "./publicApi";

const SESSION_KEY = "central_galo_access_session";
const CLIENT_KEY = "central_galo_access_client";

export function getAnalyticsClientId(): string {
  if (typeof window === "undefined") return "";

  const current = window.localStorage.getItem(CLIENT_KEY);
  if (current) return current;

  const next =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : "00000000-0000-4000-8000-" +
        Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12);

  window.localStorage.setItem(CLIENT_KEY, next);
  return next;
}

export function getAnalyticsSessionId(): string {
  if (typeof window === "undefined") return "";

  const current = window.sessionStorage.getItem(SESSION_KEY);
  if (current) return current;

  const next =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : "00000000-0000-4000-8000-" +
        Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12);

  window.sessionStorage.setItem(SESSION_KEY, next);
  return next;
}

export async function registrarCliqueAnalytics(params: {
  tipo: "noticia" | "youtube";
  referencia: string;
  referencia_slug?: string | null;
  item_id?: string | null;
  caminho?: string;
  destino_url?: string | null;
}) {
  if (typeof window === "undefined") return;

  const caminho = params.caminho ?? window.location.pathname;

  await publicApiFetch("/api/acessos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      acao: "clique",
      sessao_id: getAnalyticsSessionId(),
      cliente_id: getAnalyticsClientId(),
      caminho,
      tipo: params.tipo,
      referencia: params.referencia,
      referencia_slug: params.referencia_slug ?? null,
      item_id: params.item_id ?? null,
      destino_url: params.destino_url ?? null,
    }),
    keepalive: true,
  });
}
