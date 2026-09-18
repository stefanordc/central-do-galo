"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { getAnalyticsSessionId } from "../lib/analytics";
import { publicApiFetch } from "../lib/publicApi";

const LAST_EVENT_KEY = "central_galo_access_last";

function novoUuid(): string {
  return typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : "00000000-0000-4000-8000-" +
        Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12);
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
          now - last.at < 1500
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

    const sessaoId = getAnalyticsSessionId();
    const eventoId = novoUuid();

    let acumuladoMs = 0;
    let inicioVisivel =
      document.visibilityState === "visible" ? performance.now() : null;

    const duracaoAtual = () => {
      const atual =
        inicioVisivel == null ? 0 : Math.max(0, performance.now() - inicioVisivel);

      return Math.max(0, Math.floor((acumuladoMs + atual) / 1000));
    };

    const enviar = (acao: "inicio" | "ping") => {
      void publicApiFetch("/api/acessos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          acao,
          caminho: pathname,
          sessao_id: sessaoId,
          evento_id: eventoId,
          duracao_segundos: duracaoAtual(),
        }),
        keepalive: true,
      }).catch(() => {
        // Analytics nunca deve bloquear a navegação.
      });
    };

    enviar("inicio");

    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        if (inicioVisivel != null) {
          acumuladoMs += Math.max(0, performance.now() - inicioVisivel);
          inicioVisivel = null;
        }
        enviar("ping");
      } else if (inicioVisivel == null) {
        inicioVisivel = performance.now();
      }
    };

    const onPageHide = () => {
      if (inicioVisivel != null) {
        acumuladoMs += Math.max(0, performance.now() - inicioVisivel);
        inicioVisivel = null;
      }
      enviar("ping");
    };

    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("pagehide", onPageHide);

    const intervalId = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        enviar("ping");
      }
    }, 15000);

    return () => {
      if (inicioVisivel != null) {
        acumuladoMs += Math.max(0, performance.now() - inicioVisivel);
        inicioVisivel = null;
      }

      enviar("ping");
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, [pathname]);

  return null;
}
