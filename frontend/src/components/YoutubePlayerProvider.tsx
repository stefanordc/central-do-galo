"use client";

import {
  createContext,
  ReactNode,
  useContext,
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
    return url.toString();
  } catch {
    const separator = raw.includes("?") ? "&" : "?";
    return `${raw}${separator}autoplay=1&playsinline=1&rel=0`;
  }
}

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
            {foraDaPaginaVideos ? "Reproduzindo em segundo plano" : video.fonte_nome}
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

      <div className="youtube-player-frame">
        <iframe
          key={video.video_id}
          src={buildEmbedUrl(video)}
          title={video.titulo}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          referrerPolicy="strict-origin-when-cross-origin"
          allowFullScreen
        />
      </div>
    </section>
  );
}

export default function YoutubePlayerProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [video, setVideo] = useState<GlobalYoutubeVideo | null>(null);

  const value = useMemo<YoutubePlayerContextValue>(
    () => ({
      video,
      playVideo: setVideo,
      closeVideo: () => setVideo(null),
    }),
    [video]
  );

  return (
    <YoutubePlayerContext.Provider value={value}>
      {children}
      <PersistentYoutubePlayer video={video} onClose={() => setVideo(null)} />
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
