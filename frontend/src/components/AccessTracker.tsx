"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { publicApiFetch } from "../lib/publicApi";

const SESSION_KEY = "central_galo_access_session";
const LAST_EVENT_KEY = "central_galo_access_last";

function getSessionId(): string {
  const current = window.sessionStorage.getItem(SESSION_KEY);
  if (current) return current;

  const next =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : "00000000-0000-4000-8000-" + Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12);

  window.sessionStorage.setItem(SESSION_KEY, next);
  return next;
}

export default function AccessTracker() {
  const pathname = usePathname();
  const lastPathRef = useRef<string | null>(null);

  useEffect(() => {
    if (!pathname || pathname.startsWith("/admin")) return;
    if (lastPathRef.current === pathname) return;

    const now = Date.now();
    const lastRaw = window.sessionStorage.getItem(LAST_EVENT_KEY);
    if (lastRaw) {
      try {
        const last = JSON.parse(lastRaw) as { path?: string; at?: number };
        if (
          last.path === pathname &&
          typeof last.at === "number" &&
          now - last.at < 5000
        ) {
          lastPathRef.current = pathname;
          return;
        }
      } catch {
        // Ignora valor antigo/corrompido.
      }
    }

    lastPathRef.current = pathname;
    window.sessionStorage.setItem(
      LAST_EVENT_KEY,
      JSON.stringify({ path: pathname, at: now })
    );

    const controller = new AbortController();

    void publicApiFetch("/api/acessos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        caminho: pathname,
        sessao_id: getSessionId(),
      }),
      signal: controller.signal,
      keepalive: true,
    }).catch(() => {
      // Métrica não pode interferir na navegação do usuário.
    });

    return () => controller.abort();
  }, [pathname]);

  return null;
}
