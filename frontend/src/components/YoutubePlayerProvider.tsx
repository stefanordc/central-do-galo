"use client";

import {
  createContext,
  memo,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";

export type GlobalYoutubeVideo = {
  id: string;
  video_id: string;
  titulo: string;
  url: string;
  tipo: "video" | "short" | "live";
  fonte_nome: string;
  fonte_slug: string;
  metadados: Record<string, unknown>;
};

type YoutubePlayerContextValue = {
  video: GlobalYoutubeVideo | null;
  playVideo: (video: GlobalYoutubeVideo) => void;
  closeVideo: () => void;
};

const YoutubePlayerContext = createContext<YoutubePlayerContextValue | null>(null);
const PLAYER_SESSION_KEY = "central-do-galo:youtube-player";

function buildEmbedUrl(video: GlobalYoutubeVideo): string {
  const raw =
    typeof video.metadados?.embed_url === "string" && video.metadados.embed_url.trim()
      ? video.metadados.embed_url.trim()
      : `https://www.youtube.com/embed/${video.video_id}`;

  try {
    const url = new URL(raw);
    url.searchParams.set("autoplay", "1");
    url.searchParams.set("playsinline", "1");
    url.searchParams.set("rel", "0");
    url.searchParams.set("enablejsapi", "1");

    if (typeof window !== "undefined") {
      url.searchParams.set("origin", window.location.origin);
    }

    return url.toString();
  } catch {
    const separator = raw.includes("?") ? "&" : "?";
    return `${raw}${separator}autoplay=1&playsinline=1&rel=0&enablejsapi=1`;
  }
}

function restaurarVideoDaSessao(): GlobalYoutubeVideo | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = window.sessionStorage.getItem(PLAYER_SESSION_KEY);
    if (!raw) return null;

    const value = JSON.parse(raw) as Partial<GlobalYoutubeVideo>;
    if (
      typeof value.video_id !== "string" ||
      !value.video_id.trim() ||
      typeof value.titulo !== "string" ||
      typeof value.id !== "string"
    ) {
      window.sessionStorage.removeItem(PLAYER_SESSION_KEY);
      return null;
    }

    return {
      id: value.id,
      video_id: value.video_id,
      titulo: value.titulo,
      url: typeof value.url === "string" ? value.url : `https://www.youtube.com/watch?v=${value.video_id}`,
      tipo:
        value.tipo === "short" || value.tipo === "live"
          ? value.tipo
          : "video",
      fonte_nome: typeof value.fonte_nome === "string" ? value.fonte_nome : "YouTube",
      fonte_slug: typeof value.fonte_slug === "string" ? value.fonte_slug : "",
      metadados:
        value.metadados && typeof value.metadados === "object"
          ? value.metadados
          : {},
    };
  } catch {
    window.sessionStorage.removeItem(PLAYER_SESSION_KEY);
    return null;
  }
}

const PersistentYoutubeFrame = memo(function PersistentYoutubeFrame({
  video,
}: {
  video: GlobalYoutubeVideo;
}) {
  const embedUrl = useMemo(
    () => buildEmbedUrl(video),
    [video.video_id, video.metadados]
  );

  return (
    <div className="youtube-player-frame">
      <iframe
        src={embedUrl}
        title={video.titulo}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        referrerPolicy="strict-origin-when-cross-origin"
        allowFullScreen
      />
    </div>
  );
});

function PersistentYoutubePlayer({
  video,
  onClose,
}: {
  video: GlobalYoutubeVideo | null;
  onClose: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();

  if (!video) return null;

  const foraDaPaginaVideos = pathname !== "/videos";

  return (
    <section
      id="youtube-player"
      className={
        foraDaPaginaVideos
          ? "youtube-player-shell global-youtube-player mini"
          : "youtube-player-shell global-youtube-player expanded"
      }
      aria-label="Player persistente de vídeo"
    >
      <div className="youtube-player-topbar">
        <div>
          <span>
            {foraDaPaginaVideos ? "Continuando reprodução" : video.fonte_nome}
          </span>
          <strong>{video.titulo}</strong>
        </div>

        <div className="youtube-player-actions">
          {foraDaPaginaVideos && (
            <button
              type="button"
              onClick={() => router.push("/videos")}
              title="Voltar para Vídeos"
              aria-label="Voltar para a página de vídeos"
            >
              ↗
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            title="Fechar vídeo"
            aria-label="Fechar vídeo"
          >
            ×
          </button>
        </div>
      </div>

      <PersistentYoutubeFrame video={video} />
    </section>
  );
}

export default function YoutubePlayerProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [video, setVideo] = useState<GlobalYoutubeVideo | null>(null);

  useEffect(() => {
    const restaurado = restaurarVideoDaSessao();
    if (restaurado) {
      setVideo(restaurado);
    }
  }, []);

  const playVideo = useCallback((novoVideo: GlobalYoutubeVideo) => {
    setVideo(novoVideo);

    try {
      window.sessionStorage.setItem(
        PLAYER_SESSION_KEY,
        JSON.stringify(novoVideo)
      );
    } catch {
      // O player continua funcionando mesmo se o navegador bloquear sessionStorage.
    }
  }, []);

  const closeVideo = useCallback(() => {
    setVideo(null);

    try {
      window.sessionStorage.removeItem(PLAYER_SESSION_KEY);
    } catch {
      // Nada a fazer: o estado em memória já foi limpo.
    }
  }, []);

  const value = useMemo<YoutubePlayerContextValue>(
    () => ({
      video,
      playVideo,
      closeVideo,
    }),
    [video, playVideo, closeVideo]
  );

  return (
    <YoutubePlayerContext.Provider value={value}>
      {children}
      <PersistentYoutubePlayer video={video} onClose={closeVideo} />
    </YoutubePlayerContext.Provider>
  );
}

export function useYoutubePlayer(): YoutubePlayerContextValue {
  const context = useContext(YoutubePlayerContext);

  if (!context) {
    throw new Error("useYoutubePlayer precisa estar dentro de YoutubePlayerProvider.");
  }

  return context;
}
