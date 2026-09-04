"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type CategoriaResumo = {
  nome: string;
  slug: string;
  principal: boolean;
};

type Categoria = {
  id: string;
  nome: string;
  slug: string;
  descricao: string | null;
  ordem: number;
  total_noticias: number;
};

type Fonte = {
  id: string;
  nome: string;
  slug: string;
  tipo: string;
  confiabilidade: number;
  oficial: boolean;
  ativo: boolean;
};

type PostX = {
  id: string;
  post_id: string;
  url: string;
  texto: string | null;
  publicado_em: string | null;
  coletado_em: string;
  metricas: Record<string, number>;
  midia: Array<Record<string, unknown>>;
  embed_html: string | null;
  embed_status: string;
  embed_atualizado_em: string | null;
};

type PostXFeed = PostX & {
  conta_id: string;
  conta_nome: string;
  conta_usuario: string;
  conta_foto_url: string | null;
  conta_oficial: boolean;
};

type ContaXComPosts = {
  id: string;
  nome: string;
  usuario: string;
  foto_url: string | null;
  oficial: boolean;
  confiabilidade: number;
  ultima_sincronizacao: string | null;
  status_sync: string;
  sync_erro: string | null;
  posts: PostX[];
};

type RadarXStatus = {
  fonte: string;
  token_configurado: boolean;
  scraping_habilitado?: boolean;
  job_backend_habilitado: boolean;
  contas_ativas: number;
  nunca_sincronizadas: number;
  posts_total: number;
  embeds_ok: number;
};

type ContaXFiltro = {
  id: string;
  nome: string;
  usuario: string;
  oficial: boolean;
  confiabilidade: number;
  ativo: boolean;
};

type Noticia = {
  id: string;
  titulo: string;
  url: string;
  resumo: string | null;
  imagem_url: string | null;
  categoria: string | null;
  categorias: CategoriaResumo[];
  oficial: boolean;
  publicado_em: string | null;
  coletado_em: string;
  fonte_id: string;
  fonte_nome: string;
  fonte_slug: string;
  fonte_confiabilidade: number;
};

type VideoYoutube = {
  id: string;
  video_id: string;
  titulo: string;
  url: string;
  thumbnail_url: string | null;
  descricao: string | null;
  tipo: "video" | "short" | "live";
  publicado_em: string | null;
  coletado_em: string;
  metadados: Record<string, unknown>;
  fonte_id: string;
  fonte_nome: string;
  fonte_slug: string;
  fonte_oficial: boolean;
};

type VideoStatus = {
  total: number;
  videos: number;
  shorts: number;
  lives: number;
  ultima_coleta: string | null;
  job_habilitado: boolean;
  intervalo_segundos: number;
  itens_por_secao: number;
};

type CapaSiteConfig = {
  ativo: boolean;
  tipo: "imagem" | "video";
  media_url: string | null;
  atualizado_em: string | null;
};

type GolJogo = {
  team_id: number | null;
  time: string | null;
  time_logo: string | null;
  jogador_id: number | null;
  jogador: string | null;
  assistencia_id: number | null;
  assistencia: string | null;
  minuto: number | null;
  acrescimos: number | null;
  detalhe: string | null;
  comentarios: string | null;
};

type JogoCalendario = {
  id: string;
  id_externo: string | null;
  inicio_em: string;
  status: "agendado" | "ao_vivo" | "finalizado" | "adiado";
  status_api: string | null;
  resultado:
    | "vitoria"
    | "empate"
    | "derrota"
    | "agendado"
    | "ao_vivo"
    | "finalizado";
  rodada: string | null;
  estadio: string | null;
  cidade: string | null;
  mandante: {
    nome: string;
    logo_url: string | null;
    gols: number | null;
  };
  visitante: {
    nome: string;
    logo_url: string | null;
    gols: number | null;
  };
  galo_casa: boolean;
  galo_logo_url: string | null;
  adversario: {
    nome: string;
    logo_url: string | null;
    gols: number | null;
  };
  gols_galo: number | null;
  competicao: {
    nome: string | null;
    temporada: string | null;
    logo_url: string | null;
  };
  gols: GolJogo[];
};

type StatusJogos = {
  total: number;
  finalizados: number;
  agendados: number;
  ao_vivo: number;
  primeiro_jogo: string | null;
  ultimo_jogo: string | null;
  atualizado_em: string | null;
  api_configurada: boolean;
};

const API_URL = "/backend";
const PAGE_SIZE = 60;
const X_PAGE_SIZE = 20;
const YOUTUBE_PAGE_SIZE = 13;
const FALLBACK_NEWS_IMAGE = "/central-do-galo-logo.png";

function usarLogoComoFallback(noticia: Noticia): boolean {
  const imagem = noticia.imagem_url?.trim() ?? "";

  // O No Ataque é descoberto por índice externo e não fornece uma imagem oficial
  // confiável para o nosso coletor. Enquanto isso, usamos a identidade do portal.
  if (noticia.fonte_slug === "noataque-atletico") {
    return true;
  }

  if (!imagem) {
    return true;
  }

  // Rejeita o ícone genérico do Google News que pode ser confundido com thumbnail.
  if (
    imagem.includes("googleusercontent.com/J6_coFbogxhRI9iM864NL_liGXvsQp2AupsKei7z0cNNfDvGUmWUy20nuUhkREQyrpY4bEeIBuc")
  ) {
    return true;
  }

  return false;
}

declare global {
  interface Window {
    twttr?: {
      widgets?: {
        load: (element?: HTMLElement) => void;
      };
    };
  }
}

let xScriptPromise: Promise<void> | null = null;

function carregarScriptX(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.twttr?.widgets) return Promise.resolve();
  if (xScriptPromise) return xScriptPromise;

  xScriptPromise = new Promise<void>((resolve, reject) => {
    let script = document.getElementById("x-wjs") as HTMLScriptElement | null;

    const aguardarWidgets = () => {
      const inicio = Date.now();
      const timer = window.setInterval(() => {
        if (window.twttr?.widgets) {
          window.clearInterval(timer);
          resolve();
          return;
        }

        if (Date.now() - inicio > 8000) {
          window.clearInterval(timer);
          reject(new Error("widgets.js do X não ficou disponível."));
        }
      }, 120);
    };

    if (!script) {
      script = document.createElement("script");
      script.id = "x-wjs";
      script.src = "https://platform.x.com/widgets.js";
      script.async = true;
      script.charset = "utf-8";
      document.body.appendChild(script);
    }

    if (script.dataset.loaded === "true") {
      aguardarWidgets();
      return;
    }

    script.addEventListener(
      "load",
      () => {
        if (script) script.dataset.loaded = "true";
        aguardarWidgets();
      },
      { once: true }
    );
    script.addEventListener("error", () => reject(new Error("Falha ao carregar widgets.js do X.")), {
      once: true,
    });
  }).catch((error) => {
    xScriptPromise = null;
    throw error;
  });

  return xScriptPromise!;
}

function XPostFallback({ conta, post }: { conta: ContaXComPosts; post?: PostX }) {
  const destino = post?.url ?? `https://x.com/${conta.usuario}`;
  const mensagemSemPost =
    conta.status_sync === "config_erro"
      ? "A integração com a X API ainda não está configurada no servidor."
      : conta.status_sync === "erro"
        ? "A última sincronização desta conta falhou."
        : conta.status_sync === "pendente"
          ? "Aguardando a primeira sincronização desta conta."
          : "Nenhuma publicação cacheada no momento.";

  return (
    <a
      className="x-post-fallback"
      href={destino}
      target="_blank"
      rel="noopener noreferrer"
    >
      <div className="x-fallback-account">
        {conta.foto_url ? (
          <img src={conta.foto_url} alt="" referrerPolicy="no-referrer" />
        ) : (
          <div className="x-fallback-avatar">X</div>
        )}
        <div>
          <strong>{conta.nome}</strong>
          <span>@{conta.usuario}</span>
        </div>
      </div>
      {post?.texto ? <p>{post.texto}</p> : <p>{mensagemSemPost}</p>}
      <span className="x-fallback-link">
        {post ? "Abrir publicação no X ↗" : `Ver publicações de @${conta.usuario} no X ↗`}
      </span>
    </a>
  );
}

function XPostEmbed({ conta, post }: { conta: ContaXComPosts; post: PostX }) {
  const ref = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"carregando" | "ok" | "erro">(
    post.embed_html && post.embed_status === "ok" ? "carregando" : "erro"
  );

  useEffect(() => {
    const container = ref.current;
    if (!container || !post.embed_html || post.embed_status !== "ok") {
      setStatus("erro");
      return;
    }

    let ativo = true;
    let poll: number | undefined;
    let limite: number | undefined;

    carregarScriptX()
      .then(() => {
        if (!ativo || !ref.current) return;
        window.twttr?.widgets?.load(ref.current);

        poll = window.setInterval(() => {
          if (!ativo || !ref.current) return;
          const iframe = ref.current.querySelector("iframe");
          if (iframe) {
            if (poll) window.clearInterval(poll);
            if (limite) window.clearTimeout(limite);
            setStatus("ok");
          }
        }, 150);

        limite = window.setTimeout(() => {
          if (poll) window.clearInterval(poll);
          if (ativo) setStatus("erro");
        }, 6500);
      })
      .catch(() => {
        if (ativo) setStatus("erro");
      });

    return () => {
      ativo = false;
      if (poll) window.clearInterval(poll);
      if (limite) window.clearTimeout(limite);
    };
  }, [post.embed_html, post.embed_status, post.id]);

  if (status === "erro") {
    return <XPostFallback conta={conta} post={post} />;
  }

  return (
    <div className="x-native-post-shell">
      {status === "carregando" && <div className="x-post-loading">Carregando publicação...</div>}
      <div
        ref={ref}
        className={status === "ok" ? "x-native-post rendered" : "x-native-post"}
        dangerouslySetInnerHTML={{ __html: post.embed_html ?? "" }}
      />
    </div>
  );
}

function XAccountCard({ conta }: { conta: ContaXComPosts }) {
  return (
    <article className="x-account-card">
      <a
        className="x-account-card-header"
        href={`https://x.com/${conta.usuario}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        {conta.foto_url ? (
          <img src={conta.foto_url} alt="" referrerPolicy="no-referrer" />
        ) : (
          <div className="x-account-avatar-placeholder">X</div>
        )}
        <div className="x-account-card-copy">
          <strong>{conta.nome}</strong>
          <span>@{conta.usuario}</span>
        </div>
        {conta.oficial && <span className="x-official-label">OFICIAL</span>}
        <span className="x-open-arrow">↗</span>
      </a>

      <div className="x-account-posts">
        {conta.posts.length > 0 ? (
          conta.posts.map((post, index) => (
            <div className="x-post-item" key={post.id}>
              <div className="x-post-item-heading">
                <span>PUBLICAÇÃO {index + 1}</span>
                <span>{index + 1}/{conta.posts.length}</span>
              </div>
              <XPostEmbed conta={conta} post={post} />
            </div>
          ))
        ) : (
          <XPostFallback conta={conta} />
        )}
      </div>
    </article>
  );
}

function XMediaGallery({
  midia,
  postUrl,
}: {
  midia: Array<Record<string, unknown>>;
  postUrl: string;
}) {
  const imagens = midia
    .map((item) => ({
      tipo: typeof item.type === "string" ? item.type : "",
      url: typeof item.url === "string" ? item.url : "",
    }))
    .filter((item) =>
      item.url && ["photo", "image", "video", "video_thumbnail"].includes(item.tipo)
    )
    .slice(0, 4);

  if (imagens.length === 0) return null;

  return (
    <div className={`x-timeline-media x-timeline-media-${imagens.length}`}>
      {imagens.map((imagem, index) => (
        <a
          href={postUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="x-timeline-media-item"
          key={`${imagem.url}-${index}`}
        >
          <img
            src={`/backend/api/x/media?url=${encodeURIComponent(imagem.url)}`}
            alt="Imagem anexada à publicação no X"
            loading="lazy"
          />
        </a>
      ))}
    </div>
  );
}

function formatarNumeroX(valor: number | undefined): string {
  if (!valor || valor <= 0) return "";
  return new Intl.NumberFormat("pt-BR", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(valor);
}

function prepararEmbedXParaNovaAba(html: string): string {
  return html.replace(/<a\b([^>]*)>/gi, (_match, atributos: string) => {
    const semTarget = atributos
      .replace(/\s+target=(?:"[^"]*"|\'[^\']*\'|[^\s>]+)/gi, "")
      .replace(/\s+rel=(?:"[^"]*"|\'[^\']*\'|[^\s>]+)/gi, "");
    return `<a${semTarget} target="_blank" rel="noopener noreferrer">`;
  });
}

function corpoDoOEmbedX(html: string | null): string | null {
  if (!html) return null;
  const match = html.match(/<p\b[^>]*>([\s\S]*?)<\/p>/i);
  if (!match?.[1]) return null;
  return prepararEmbedXParaNovaAba(match[1]);
}

function XTimelineNativeEmbed({ post }: { post: PostXFeed }) {
  const embedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let ativo = true;

    carregarScriptX()
      .then(() => {
        if (!ativo || !embedRef.current) return;

        // Importante: depois que o widgets.js transforma o blockquote em iframe,
        // este componente não atualiza estado. Assim o React não sobrescreve
        // o DOM que passou a ser controlado pelo widget nativo do X.
        window.requestAnimationFrame(() => {
          if (!ativo || !embedRef.current) return;
          window.twttr?.widgets?.load(embedRef.current);
        });
      })
      .catch(() => {
        // O HTML do oEmbed permanece como fallback quando o script do X falha.
      });

    return () => {
      ativo = false;
    };
  }, [post.id]);

  return (
    <div
      ref={embedRef}
      className="x-timeline-native-embed"
      dangerouslySetInnerHTML={{ __html: prepararEmbedXParaNovaAba(post.embed_html ?? "") }}
    />
  );
}

function XTimelineEmbed({ post, ativado }: { post: PostXFeed; ativado: boolean }) {
  if (!post.embed_html || post.embed_status !== "ok") {
    if (post.texto) {
      return <p className="x-timeline-text">{post.texto}</p>;
    }

    return (
      <p className="x-timeline-text x-timeline-text-muted">
        Publicação disponível no X.
      </p>
    );
  }

  if (!ativado) {
    return (
      <div className="x-timeline-embed-preview">
        {post.texto ? <p>{post.texto}</p> : <p>Publicação disponível no X.</p>}
        <span>Conteúdo visual será carregado em instantes.</span>
      </div>
    );
  }

  return <XTimelineNativeEmbed post={post} />;
}

function XTimelineItem({ post }: { post: PostXFeed }) {
  const corpoHtml = corpoDoOEmbedX(post.embed_html);

  return (
    <article className="x-timeline-item">
      <div className="x-timeline-avatar-wrap" aria-hidden="true">
        {post.conta_foto_url ? (
          <img
            className="x-timeline-avatar"
            src={post.conta_foto_url}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="x-timeline-avatar x-timeline-avatar-placeholder">X</div>
        )}
      </div>

      <div className="x-timeline-card x-timeline-card-native">
        <div className="x-timeline-meta-bar">
          <div className="x-timeline-meta-author">
            <strong>{post.conta_nome}</strong>
            {post.conta_oficial && <span className="x-timeline-official">OFICIAL</span>}
            <span>@{post.conta_usuario}</span>
          </div>
          <time dateTime={post.publicado_em ?? post.coletado_em}>
            {formatarData(post.publicado_em, post.coletado_em)}
          </time>
        </div>

        <div className="x-timeline-content-cache">
          {corpoHtml ? (
            <div
              className="x-timeline-text x-timeline-rich-text"
              dangerouslySetInnerHTML={{ __html: corpoHtml }}
            />
          ) : post.texto ? (
            <p className="x-timeline-text">{post.texto}</p>
          ) : (
            <p className="x-timeline-text x-timeline-text-muted">Publicação disponível no X.</p>
          )}

          <XMediaGallery midia={post.midia} postUrl={post.url} />
        </div>

        <div className="x-timeline-native-footer">
          <a href={post.url} target="_blank" rel="noopener noreferrer">
            Ver no X <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    </article>
  );
}

function formatarData(data: string | null, coletadoEm: string): string {
  const valor = data ?? coletadoEm;
  const date = new Date(valor);

  if (Number.isNaN(date.getTime())) {
    return "Agora";
  }

  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatarDuracaoVideo(valor: unknown): string | null {
  if (typeof valor !== "number" || !Number.isFinite(valor) || valor <= 0) return null;
  const total = Math.round(valor);
  const horas = Math.floor(total / 3600);
  const minutos = Math.floor((total % 3600) / 60);
  const segundos = total % 60;
  if (horas > 0) {
    return `${horas}:${String(minutos).padStart(2, "0")}:${String(segundos).padStart(2, "0")}`;
  }
  return `${minutos}:${String(segundos).padStart(2, "0")}`;
}

function rotuloLive(video: VideoYoutube): string {
  const status = typeof video.metadados.live_status === "string" ? video.metadados.live_status : "";
  if (status === "is_live") return "AO VIVO";
  if (status === "is_upcoming") return "EM BREVE";
  return "TRANSMISSÃO";
}

function VideoCard({ video, onPlay }: { video: VideoYoutube; onPlay: (video: VideoYoutube) => void }) {
  const duracao = formatarDuracaoVideo(video.metadados.duration);
  const thumbnail = video.thumbnail_url || `https://i.ytimg.com/vi/${video.video_id}/hqdefault.jpg`;
  const liveLabel = video.tipo === "live" ? rotuloLive(video) : null;
  const liveAgora = liveLabel === "AO VIVO";

  return (
    <article className={`youtube-card youtube-card-${video.tipo}`}>
      <button
        className="youtube-card-play"
        type="button"
        onClick={() => onPlay(video)}
        aria-label={`Reproduzir ${video.titulo}`}
      >
        <span className="youtube-thumb-wrap">
          <img src={thumbnail} alt="" loading="lazy" referrerPolicy="no-referrer" />
          <span className="youtube-play-mark" aria-hidden="true">▶</span>
          {duracao && video.tipo !== "live" && <span className="youtube-duration">{duracao}</span>}
          {liveLabel && (
            <span className={liveAgora ? "youtube-live-badge is-live-now" : "youtube-live-badge"}>
              {liveLabel}
            </span>
          )}
          {video.tipo === "short" && <span className="youtube-short-badge">SHORT</span>}
        </span>
        <span className="youtube-card-copy">
          <strong>{video.titulo}</strong>
          <span>{video.fonte_nome}</span>
          {video.publicado_em && <time>{formatarData(video.publicado_em, video.coletado_em)}</time>}
        </span>
      </button>
    </article>
  );
}

function VideoShelf({
  titulo,
  subtitulo,
  items,
  variant,
  onPlay,
}: {
  titulo: string;
  subtitulo: string;
  items: VideoYoutube[];
  variant: "video" | "short" | "live";
  onPlay: (video: VideoYoutube) => void;
}) {
  if (items.length === 0) return null;

  return (
    <section className={`youtube-shelf youtube-shelf-${variant}`}>
      <div className="youtube-shelf-heading">
        <div>
          <h3>{titulo}</h3>
          <p>{subtitulo}</p>
        </div>
        <span>{items.length} publicações</span>
      </div>
      <div className={`youtube-grid youtube-grid-${variant}`}>
        {items.map((video) => <VideoCard video={video} onPlay={onPlay} key={video.id} />)}
      </div>
    </section>
  );
}

function YoutubePersistentPlayer({
  video,
  mini,
  onClose,
  onReturn,
}: {
  video: VideoYoutube | null;
  mini: boolean;
  onClose: () => void;
  onReturn: () => void;
}) {
  if (!video) return null;

  return (
    <section
      id="youtube-player"
      className={mini ? "youtube-player-shell mini" : "youtube-player-shell"}
      aria-label="Player de vídeo"
    >
      <div className="youtube-player-topbar">
        <div>
          <span>{mini ? "Reproduzindo" : video.fonte_nome}</span>
          <strong>{video.titulo}</strong>
        </div>
        <div className="youtube-player-actions">
          {mini && (
            <button type="button" onClick={onReturn} title="Voltar para Vídeos">
              ↗
            </button>
          )}
          <button type="button" onClick={onClose} title="Fechar vídeo" aria-label="Fechar vídeo">
            ×
          </button>
        </div>
      </div>
      <div className="youtube-player-frame">
        <iframe
          key={video.video_id}
          src={`${typeof video.metadados.embed_url === "string" ? video.metadados.embed_url : `https://www.youtube.com/embed/${video.video_id}`}?autoplay=1&playsinline=1&rel=0`}
          title={video.titulo}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          referrerPolicy="strict-origin-when-cross-origin"
          allowFullScreen
        />
      </div>
    </section>
  );
}

function normalizarBusca(valor: string): string {
  return valor
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

const MESES_PT = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

const DIAS_SEMANA = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"];

function inicioDoMes(data: Date): Date {
  return new Date(data.getFullYear(), data.getMonth(), 1);
}

function fimDoMes(data: Date): Date {
  return new Date(data.getFullYear(), data.getMonth() + 1, 0);
}

function chaveDataLocal(data: Date): string {
  const ano = data.getFullYear();
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

function formatarHorarioJogo(valor: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(valor));
}

function formatarDataCompletaJogo(valor: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(valor));
}

function resultadoClasse(jogo: JogoCalendario | undefined): string {
  if (!jogo) return "";
  if (jogo.resultado === "vitoria") return "game-day-win";
  if (jogo.resultado === "empate") return "game-day-draw";
  if (jogo.resultado === "derrota") return "game-day-loss";
  if (jogo.resultado === "ao_vivo") return "game-day-live";
  return jogo.status === "agendado" ? "game-day-future" : "";
}

function placarJogo(jogo: JogoCalendario): string {
  if (
    jogo.mandante.gols === null ||
    jogo.visitante.gols === null
  ) {
    return "x";
  }

  return `${jogo.mandante.gols} × ${jogo.visitante.gols}`;
}

export default function Home() {
  const [noticias, setNoticias] = useState<Noticia[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [fontesDisponiveis, setFontesDisponiveis] = useState<Fonte[]>([]);
  const [canaisYoutubeDisponiveis, setCanaisYoutubeDisponiveis] = useState<Fonte[]>([]);
  const [categoriaSelecionada, setCategoriaSelecionada] = useState("");
  const [fonteSelecionada, setFonteSelecionada] = useState("");
  const [buscaDigitada, setBuscaDigitada] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [carregandoMais, setCarregandoMais] = useState(false);
  const [temMais, setTemMais] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [secaoAtiva, setSecaoAtiva] = useState<"noticias" | "videos" | "x" | "jogos">("noticias");
  const [feedX, setFeedX] = useState<PostXFeed[]>([]);
  const [statusX, setStatusX] = useState<RadarXStatus | null>(null);
  const [carregandoX, setCarregandoX] = useState(false);
  const [carregandoMaisX, setCarregandoMaisX] = useState(false);
  const [temMaisX, setTemMaisX] = useState(false);
  const [erroX, setErroX] = useState<string | null>(null);
  const [perfisX, setPerfisX] = useState<ContaXFiltro[]>([]);
  const [perfilSelecionadoX, setPerfilSelecionadoX] = useState("");
  const [buscaX, setBuscaX] = useState("");
  const [buscaVideos, setBuscaVideos] = useState("");
  const [canalSelecionadoYoutube, setCanalSelecionadoYoutube] = useState("");
  const [filtroVideos, setFiltroVideos] = useState<"video" | "short" | "live">("video");
  const [videosYoutube, setVideosYoutube] = useState<VideoYoutube[]>([]);
  const [shortsYoutube, setShortsYoutube] = useState<VideoYoutube[]>([]);
  const [livesYoutube, setLivesYoutube] = useState<VideoYoutube[]>([]);
  const [statusVideos, setStatusVideos] = useState<VideoStatus | null>(null);
  const [carregandoVideos, setCarregandoVideos] = useState(false);
  const [erroVideos, setErroVideos] = useState<string | null>(null);
  const [videoAtivo, setVideoAtivo] = useState<VideoYoutube | null>(null);
  const [capaSite, setCapaSite] = useState<CapaSiteConfig | null>(null);
  const [capaAberta, setCapaAberta] = useState(false);

  const [mesJogos, setMesJogos] = useState(() => inicioDoMes(new Date()));
  const [jogosCalendario, setJogosCalendario] = useState<JogoCalendario[]>([]);
  const [statusJogos, setStatusJogos] = useState<StatusJogos | null>(null);
  const [jogoSelecionado, setJogoSelecionado] = useState<JogoCalendario | null>(null);
  const [carregandoJogos, setCarregandoJogos] = useState(false);
  const [erroJogos, setErroJogos] = useState<string | null>(null);

  async function carregarFiltros() {
    try {
      const [categoriasResponse, fontesResponse] = await Promise.all([
        fetch(`${API_URL}/api/categorias`, { cache: "no-store" }),
        fetch(`${API_URL}/api/fontes`, { cache: "no-store" }),
      ]);

      if (categoriasResponse.ok) {
        const data: Categoria[] = await categoriasResponse.json();
        setCategorias(data);
      }

      if (fontesResponse.ok) {
        const data: Fonte[] = await fontesResponse.json();

        setFontesDisponiveis(
          data.filter((fonte) => fonte.tipo === "noticia" || fonte.tipo === "oficial")
        );

        setCanaisYoutubeDisponiveis(
          data
            .filter((fonte) => fonte.tipo === "youtube" && fonte.ativo)
            .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR", { sensitivity: "base" }))
        );
      }
    } catch {
      // A falha dos filtros não impede a listagem principal de notícias.
    }
  }

  async function carregarPerfisX() {
    try {
      const response = await fetch(`${API_URL}/api/x/contas`, { cache: "no-store" });
      if (!response.ok) return;
      const data: ContaXFiltro[] = await response.json();
      setPerfisX(
        data
          .filter((conta) => conta.ativo)
          .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR", { sensitivity: "base" }))
      );
    } catch {
      // O filtro de perfis é auxiliar e não impede a timeline de carregar.
    }
  }

  async function carregarFeedX({ append = false }: { append?: boolean } = {}) {
    if (append) {
      setCarregandoMaisX(true);
    } else {
      setCarregandoX(true);
    }

    try {
      const offset = append ? feedX.length : 0;
      const paramsX = new URLSearchParams({
        limit: String(X_PAGE_SIZE),
        offset: String(offset),
      });
      if (perfilSelecionadoX) paramsX.set("usuario", perfilSelecionadoX);

      const feedPromise = fetch(`${API_URL}/api/x/feed?${paramsX.toString()}`, {
        cache: "no-store",
      });
      const statusPromise = append
        ? Promise.resolve<Response | null>(null)
        : fetch(`${API_URL}/api/x/status`, { cache: "no-store" });

      const [feedResponse, statusResponse] = await Promise.all([feedPromise, statusPromise]);

      if (!feedResponse.ok) {
        throw new Error(`API da timeline respondeu ${feedResponse.status}`);
      }

      const data: PostXFeed[] = await feedResponse.json();
      setFeedX((atuais) => {
        if (!append) return data;
        const ids = new Set(atuais.map((post) => post.id));
        return [...atuais, ...data.filter((post) => !ids.has(post.id))];
      });
      setTemMaisX(data.length === X_PAGE_SIZE);

      if (statusResponse?.ok) {
        const statusData: RadarXStatus = await statusResponse.json();
        setStatusX(statusData);
      }

      setErroX(null);
    } catch (error) {
      const mensagem = error instanceof Error ? error.message : "Falha ao carregar a timeline do X";
      setErroX(mensagem);
    } finally {
      setCarregandoX(false);
      setCarregandoMaisX(false);
    }
  }

  async function carregarVideosYoutube() {
    if (canaisYoutubeDisponiveis.length === 0) {
      return;
    }

    setCarregandoVideos(true);

    try {
      const carregarTipoPorCanal = async (tipo: VideoYoutube["tipo"]) => {
        const responses = await Promise.all(
          canaisYoutubeDisponiveis.map((fonte) =>
            fetch(
              `${API_URL}/api/videos?tipo=${tipo}&limit=${YOUTUBE_PAGE_SIZE}&offset=0&fonte=${encodeURIComponent(fonte.slug)}`,
              { cache: "no-store" }
            )
          )
        );

        const falha = responses.find((response) => !response.ok);
        if (falha) {
          throw new Error(`API de vídeos respondeu ${falha.status}`);
        }

        const blocos = await Promise.all(
          responses.map((response) => response.json() as Promise<VideoYoutube[]>)
        );

        return blocos
          .flat()
          .sort((a, b) => {
            const dataA = new Date(a.publicado_em ?? a.coletado_em).getTime();
            const dataB = new Date(b.publicado_em ?? b.coletado_em).getTime();
            return dataB - dataA;
          });
      };

      const [videosData, shortsData, livesData, statusResponse] = await Promise.all([
        carregarTipoPorCanal("video"),
        carregarTipoPorCanal("short"),
        carregarTipoPorCanal("live"),
        fetch(`${API_URL}/api/videos/status`, { cache: "no-store" }),
      ]);

      setVideosYoutube(videosData);
      setShortsYoutube(shortsData);
      setLivesYoutube(livesData);

      if (statusResponse.ok) {
        setStatusVideos(await statusResponse.json());
      }

      setErroVideos(null);
    } catch (error) {
      const mensagem = error instanceof Error ? error.message : "Falha ao carregar vídeos";
      setErroVideos(mensagem);
    } finally {
      setCarregandoVideos(false);
    }
  }

  function reproduzirVideo(video: VideoYoutube) {
    setVideoAtivo(video);
    window.requestAnimationFrame(() => {
      document.getElementById("youtube-player")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function montarParametros(offset: number) {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(offset),
    });
    if (categoriaSelecionada) params.set("categoria", categoriaSelecionada);
    if (fonteSelecionada) params.set("fonte", fonteSelecionada);
    if (buscaAplicada.trim().length >= 2) params.set("q", buscaAplicada.trim());
    return params;
  }

  async function carregarNoticias({ append = false }: { append?: boolean } = {}) {
    if (append) {
      setCarregandoMais(true);
    } else {
      setCarregando(true);
    }

    try {
      const offset = append ? noticias.length : 0;
      const params = montarParametros(offset);
      const response = await fetch(`${API_URL}/api/noticias?${params.toString()}`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`API respondeu ${response.status}`);
      }

      const data: Noticia[] = await response.json();
      setNoticias((atuais) => (append ? [...atuais, ...data] : data));
      setTemMais(data.length === PAGE_SIZE);
      setErro(null);
    } catch (error) {
      const mensagem = error instanceof Error ? error.message : "Falha ao acessar a API";
      setErro(mensagem);
    } finally {
      setCarregando(false);
      setCarregandoMais(false);
    }
  }

  async function carregarJogos(mes = mesJogos) {
    setCarregandoJogos(true);

    try {
      const inicio = inicioDoMes(mes);
      const fim = fimDoMes(mes);

      const params = new URLSearchParams({
        inicio: chaveDataLocal(inicio),
        fim: chaveDataLocal(fim),
      });

      const [jogosResponse, statusResponse] = await Promise.all([
        fetch(`${API_URL}/api/jogos?${params.toString()}`, {
          cache: "no-store",
        }),
        fetch(`${API_URL}/api/jogos/status`, {
          cache: "no-store",
        }),
      ]);

      if (!jogosResponse.ok) {
        throw new Error(`API de jogos respondeu ${jogosResponse.status}`);
      }

      const jogos: JogoCalendario[] = await jogosResponse.json();
      setJogosCalendario(jogos);

      if (statusResponse.ok) {
        setStatusJogos(await statusResponse.json());
      }

      setErroJogos(null);
    } catch (error) {
      setErroJogos(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar o calendário de jogos."
      );
    } finally {
      setCarregandoJogos(false);
    }
  }

  useEffect(() => {
    let ativo = true;

    fetch(`${API_URL}/api/admin/capa-publica`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return null;
        return response.json() as Promise<CapaSiteConfig>;
      })
      .then((data) => {
        if (!ativo || !data) return;

        setCapaSite(data);

        if (data.ativo && data.media_url) {
          setCapaAberta(true);
        }
      })
      .catch(() => {
        // A capa é opcional. Falha nela não impede o restante do site.
      });

    return () => {
      ativo = false;
    };
  }, []);

  useEffect(() => {
    if (!capaAberta) return;

    const fecharComEsc = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setCapaAberta(false);
      }
    };

    window.addEventListener("keydown", fecharComEsc);
    return () => window.removeEventListener("keydown", fecharComEsc);
  }, [capaAberta]);

  useEffect(() => {
    if (!jogoSelecionado) return;

    const fecharDetalheJogo = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setJogoSelecionado(null);
      }
    };

    window.addEventListener("keydown", fecharDetalheJogo);
    return () => window.removeEventListener("keydown", fecharDetalheJogo);
  }, [jogoSelecionado]);

  useEffect(() => {
    carregarFiltros();
    carregarPerfisX();
  }, []);

  useEffect(() => {
    if (secaoAtiva !== "noticias") return;

    carregarNoticias();
    const interval = window.setInterval(() => carregarNoticias(), 60_000);
    return () => window.clearInterval(interval);
  }, [categoriaSelecionada, fonteSelecionada, buscaAplicada, secaoAtiva]);

  useEffect(() => {
    if (secaoAtiva !== "videos" || canaisYoutubeDisponiveis.length === 0) return;

    carregarVideosYoutube();
    const interval = window.setInterval(() => carregarVideosYoutube(), 60_000);
    return () => window.clearInterval(interval);
  }, [secaoAtiva, canaisYoutubeDisponiveis]);

  useEffect(() => {
    if (secaoAtiva !== "x") return;
    setFeedX([]);
    setTemMaisX(false);
    carregarFeedX();
  }, [secaoAtiva, perfilSelecionadoX]);

  useEffect(() => {
    if (secaoAtiva !== "jogos") return;
    carregarJogos(mesJogos);
  }, [secaoAtiva, mesJogos]);

  const filtroAtivo = Boolean(categoriaSelecionada || fonteSelecionada || buscaAplicada);

  function limparFiltros() {
    setCategoriaSelecionada("");
    setFonteSelecionada("");
    setBuscaDigitada("");
    setBuscaAplicada("");
  }

  function pesquisar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const valor = buscaDigitada.trim();
    setBuscaAplicada(valor.length >= 2 ? valor : "");
  }

  const termoBuscaX = normalizarBusca(buscaX);
  const feedXFiltrado = termoBuscaX
    ? feedX.filter((post) =>
        [
          post.texto ?? "",
          post.conta_nome,
          post.conta_usuario,
        ].some((valor) => normalizarBusca(valor).includes(termoBuscaX))
      )
    : feedX;

  const termoBuscaVideos = normalizarBusca(buscaVideos);

  const filtrarVideos = (items: VideoYoutube[]) =>
    items.filter((video) => {
      const correspondeCanal =
        !canalSelecionadoYoutube ||
        video.fonte_slug === canalSelecionadoYoutube;

      const correspondeBusca =
        !termoBuscaVideos ||
        [
          video.titulo,
          video.descricao ?? "",
          video.fonte_nome,
        ].some((valor) => normalizarBusca(valor).includes(termoBuscaVideos));

      return correspondeCanal && correspondeBusca;
    });

  const videosYoutubeFiltrados = filtrarVideos(videosYoutube);
  const shortsYoutubeFiltrados = filtrarVideos(shortsYoutube);
  const livesYoutubeFiltrados = filtrarVideos(livesYoutube);

  const configuracaoFiltroVideos = {
    video: {
      titulo: "Vídeos",
      subtitulo: "Os 13 vídeos mais recentes de cada canal.",
      items: videosYoutubeFiltrados,
      totalOriginal: videosYoutube.length,
      variant: "video" as const,
    },
    short: {
      titulo: "Reels",
      subtitulo: "Conteúdo curto publicado pelo Atlético.",
      items: shortsYoutubeFiltrados,
      totalOriginal: shortsYoutube.length,
      variant: "short" as const,
    },
    live: {
      titulo: "Ao Vivo",
      subtitulo: "Ao vivo agora, próximas transmissões e histórico recente.",
      items: livesYoutubeFiltrados,
      totalOriginal: livesYoutube.length,
      variant: "live" as const,
    },
  }[filtroVideos];

  return (
    <main className="page-shell">
      {capaAberta && capaSite?.ativo && capaSite.media_url && (
        <div
          className="site-cover-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Capa de abertura"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setCapaAberta(false);
            }
          }}
        >
          <div className="site-cover-modal">
            <button
              className="site-cover-close"
              type="button"
              onClick={() => setCapaAberta(false)}
              aria-label="Fechar"
              title="Fechar"
            >
              ×
            </button>

            {capaSite.tipo === "video" ? (
              <video
                className="site-cover-media"
                src={capaSite.media_url}
                autoPlay
                muted
                playsInline
                controls
              />
            ) : (
              <img
                className="site-cover-media"
                src={capaSite.media_url}
                alt="Capa da Central do Galo"
              />
            )}
          </div>
        </div>
      )}

      <header className="hero">
        <div className="hero-copy">
          <div className="brand-lockup">
            <img
              className="brand-logo"
              src="/central-do-galo-logo.png"
              alt="Central do Galo"
            />
            <div>
              <p className="brand-name">Central do Galo</p>
              <p className="brand-tagline">Notícias · Vídeos · X · Jogos · Dados</p>
            </div>
          </div>
          <h1>Tudo sobre o Atlético em um só lugar.</h1>
          <p className="subtitle">
            Notícias reunidas de fontes selecionadas e confiáveis, sempre levando você à publicação original.
          </p>
        </div>

      </header>

      <nav className="menu">
        <button
          className={secaoAtiva === "noticias" ? "active" : ""}
          onClick={() => setSecaoAtiva("noticias")}
        >
          Notícias
        </button>
        <button
          className={secaoAtiva === "videos" ? "active" : ""}
          onClick={() => setSecaoAtiva("videos")}
        >
          Vídeos
        </button>
        <button
          className={secaoAtiva === "x" ? "active" : ""}
          onClick={() => setSecaoAtiva("x")}
        >
          X
        </button>
        <button
          className={secaoAtiva === "jogos" ? "active" : ""}
          onClick={() => setSecaoAtiva("jogos")}
        >
          Jogos
        </button>
        <button disabled>Dados</button>
      </nav>

      <YoutubePersistentPlayer
        video={videoAtivo}
        mini={secaoAtiva !== "videos"}
        onClose={() => setVideoAtivo(null)}
        onReturn={() => setSecaoAtiva("videos")}
      />

      {secaoAtiva === "noticias" && (
        <>
      <section className="section-header">
        <div>
          <p className="eyebrow">RADAR DE NOTÍCIAS</p>
          <h2>Últimas do Galo</h2>
        </div>
        <button className="refresh-button" onClick={() => carregarNoticias()} disabled={carregando}>
          {carregando ? "Atualizando..." : "Atualizar"}
        </button>
      </section>

      <section className="filters-panel">
        <form className="search-form" onSubmit={pesquisar}>
          <label htmlFor="news-search" className="filter-label">
            Pesquisar no histórico
          </label>
          <div className="search-row">
            <input
              id="news-search"
              type="search"
              value={buscaDigitada}
              onChange={(event) => setBuscaDigitada(event.target.value)}
              placeholder="Ex.: Savinho, Fred, Arena MRV, Scarpa..."
            />
            <button type="submit">Pesquisar</button>
          </div>
        </form>

        <div className="filter-block">
          <span className="filter-label">Categoria</span>
          <div className="category-filters">
            <button
              className={!categoriaSelecionada ? "filter-chip active" : "filter-chip"}
              onClick={() => setCategoriaSelecionada("")}
            >
              Todas
            </button>

            {categorias.map((categoria) => (
              <button
                key={categoria.id}
                className={
                  categoriaSelecionada === categoria.slug ? "filter-chip active" : "filter-chip"
                }
                onClick={() => setCategoriaSelecionada(categoria.slug)}
                title={categoria.descricao ?? categoria.nome}
              >
                {categoria.nome}
                <span>{categoria.total_noticias}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="filter-source-row">
          <label>
            <span className="filter-label">Fonte</span>
            <select
              value={fonteSelecionada}
              onChange={(event) => setFonteSelecionada(event.target.value)}
            >
              <option value="">Todas as fontes</option>
              {fontesDisponiveis.map((fonte) => (
                <option value={fonte.slug} key={fonte.id}>
                  {fonte.nome}
                </option>
              ))}
            </select>
          </label>

          {filtroAtivo && (
            <button className="clear-filters" onClick={limparFiltros}>
              Limpar filtros
            </button>
          )}
        </div>

        {buscaAplicada && (
          <div className="active-search">
            Pesquisando por <strong>“{buscaAplicada}”</strong>
          </div>
        )}
      </section>

      {erro && (
        <div className="state-card error-card">
          <strong>O frontend não conseguiu acessar o backend.</strong>
          <span>
            Verifique se o FastAPI está rodando em {API_URL}. Detalhe: {erro}
          </span>
        </div>
      )}

      {!erro && carregando && noticias.length === 0 && (
        <div className="state-card">
          <strong>Carregando notícias...</strong>
        </div>
      )}

      {!erro && !carregando && noticias.length === 0 && (
        <div className="state-card">
          <strong>Nenhuma notícia encontrada.</strong>
          <span>Tente outra busca, categoria ou fonte.</span>
        </div>
      )}

      <section className="news-grid">
        {noticias.map((noticia) => {
          const categoriaPrincipal = noticia.categorias.find((categoria) => categoria.principal);
          const categoriasSecundarias = noticia.categorias.filter(
            (categoria) => !categoria.principal
          );

          return (
            <article className="news-card" key={noticia.id}>
              {(() => {
                const usarFallback = usarLogoComoFallback(noticia);

                return (
                  <img
                    className={usarFallback ? "news-image fallback-logo" : "news-image"}
                    src={usarFallback ? FALLBACK_NEWS_IMAGE : noticia.imagem_url ?? FALLBACK_NEWS_IMAGE}
                    alt={usarFallback ? "Central do Galo" : ""}
                    loading="lazy"
                    referrerPolicy="no-referrer"
                    onError={(event) => {
                      event.currentTarget.onerror = null;
                      event.currentTarget.src = FALLBACK_NEWS_IMAGE;
                      event.currentTarget.alt = "Central do Galo";
                      event.currentTarget.classList.add("fallback-logo");
                    }}
                  />
                );
              })()}

              <div className="news-body">
                <div className="news-meta">
                  <span className="source-badge">{noticia.fonte_nome}</span>
                  {noticia.oficial && <span className="official-badge">OFICIAL</span>}
                  {categoriaPrincipal && (
                    <span className="category-badge primary-category">
                      {categoriaPrincipal.nome}
                    </span>
                  )}
                  {categoriasSecundarias.slice(0, 1).map((categoria) => (
                    <span className="category-badge" key={categoria.slug}>
                      {categoria.nome}
                    </span>
                  ))}
                </div>

                <h3>{noticia.titulo}</h3>

                {noticia.resumo && <p className="news-summary">{noticia.resumo}</p>}

                <div className="news-footer">
                  <time>{formatarData(noticia.publicado_em, noticia.coletado_em)}</time>
                  <a href={noticia.url} target="_blank" rel="noopener noreferrer">
                    Ler na fonte →
                  </a>
                </div>
              </div>
            </article>
          );
        })}
      </section>

      {!erro && temMais && noticias.length > 0 && (
        <div className="load-more-wrap">
          <button
            className="load-more-button"
            onClick={() => carregarNoticias({ append: true })}
            disabled={carregandoMais}
          >
            {carregandoMais ? "Carregando..." : "Carregar mais notícias"}
          </button>
        </div>
      )}
        </>
      )}

      {secaoAtiva === "videos" && (
        <>
          <section className="section-header youtube-page-header">
            <div>
              <p className="eyebrow">GALOTV</p>
              <h2>Vídeos do Atlético</h2>
              <p className="youtube-page-copy">
                Vídeos, Reels e transmissões dos canais monitorados, reproduzidos sem sair do Central do Galo.
              </p>
            </div>
            <button
              className="refresh-button"
              type="button"
              onClick={() => carregarVideosYoutube()}
              disabled={carregandoVideos}
            >
              {carregandoVideos ? "Atualizando..." : "Atualizar"}
            </button>
          </section>

          <section className="filters-panel">
            <div className="search-form">
              <label htmlFor="video-search" className="filter-label">
                Buscar vídeos
              </label>
              <div className="search-row">
                <input
                  id="video-search"
                  type="search"
                  value={buscaVideos}
                  onChange={(event) => setBuscaVideos(event.target.value)}
                  placeholder="Buscar por termo, jogador, treino..."
                />
              </div>
            </div>

            <div className="filter-block">
              <span className="filter-label">Tipo</span>
              <div className="category-filters" aria-label="Filtrar tipo de vídeo">
                <button
                  type="button"
                  className={filtroVideos === "video" ? "filter-chip active" : "filter-chip"}
                  onClick={() => setFiltroVideos("video")}
                >
                  Vídeos
                </button>
                <button
                  type="button"
                  className={filtroVideos === "short" ? "filter-chip active" : "filter-chip"}
                  onClick={() => setFiltroVideos("short")}
                >
                  Reels
                </button>
                <button
                  type="button"
                  className={filtroVideos === "live" ? "filter-chip active" : "filter-chip"}
                  onClick={() => setFiltroVideos("live")}
                >
                  Ao Vivo
                </button>
              </div>
            </div>

            <div className="filter-source-row">
              <label>
                <span className="filter-label">Canal</span>
                <select
                  value={canalSelecionadoYoutube}
                  onChange={(event) => setCanalSelecionadoYoutube(event.target.value)}
                  aria-label="Filtrar vídeos por canal"
                >
                  <option value="">Todos os canais</option>
                  {canaisYoutubeDisponiveis.map((canal) => (
                    <option value={canal.slug} key={canal.id}>
                      {canal.nome}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </section>

          <div className="youtube-channel-strip">
            <div className="youtube-channel-mark">▶</div>
            <div>
              <strong>Canais monitorados</strong>
              <span>Conteúdo reunido automaticamente pela Central do Galo</span>
            </div>
            {statusVideos?.ultima_coleta && (
              <time>Atualizado em {formatarData(statusVideos.ultima_coleta, statusVideos.ultima_coleta)}</time>
            )}
          </div>

          {erroVideos && (
            <div className="state-card error-card">
              <strong>Não foi possível carregar os vídeos.</strong>
              <span>Detalhe: {erroVideos}</span>
            </div>
          )}

          {!erroVideos && carregandoVideos && videosYoutube.length === 0 && shortsYoutube.length === 0 && livesYoutube.length === 0 && (
            <div className="state-card">
              <strong>Carregando GaloTV...</strong>
            </div>
          )}

          {!erroVideos && !carregandoVideos && videosYoutube.length === 0 && shortsYoutube.length === 0 && livesYoutube.length === 0 && (
            <div className="state-card">
              <strong>Ainda não há vídeos sincronizados.</strong>
              <span>Execute a sincronização inicial do YouTube no backend.</span>
            </div>
          )}

          {!erroVideos &&
            !carregandoVideos &&
            configuracaoFiltroVideos.totalOriginal > 0 &&
            configuracaoFiltroVideos.items.length === 0 && (
              <div className="state-card">
                <strong>Nenhum conteúdo encontrado.</strong>
                <span>Tente outro termo de busca.</span>
              </div>
          )}

          {!erroVideos &&
            !carregandoVideos &&
            configuracaoFiltroVideos.totalOriginal === 0 && (
              <div className="state-card">
                <strong>Nenhum conteúdo disponível nesta aba.</strong>
              </div>
          )}

          {!erroVideos && configuracaoFiltroVideos.items.length > 0 && (
            <div className="youtube-home-grid">
              <VideoShelf
                titulo={configuracaoFiltroVideos.titulo}
                subtitulo={configuracaoFiltroVideos.subtitulo}
                items={configuracaoFiltroVideos.items}
                variant={configuracaoFiltroVideos.variant}
                onPlay={reproduzirVideo}
              />
            </div>
          )}
        </>
      )}

      {secaoAtiva === "x" && (
        <>
          <section className="section-header x-section-header">
            <div>
              <p className="eyebrow">RADAR DO X</p>
              <h2>Últimas do X</h2>
              <p className="x-section-copy">
                Uma timeline única com publicações dos perfis monitorados, ordenadas da mais recente para a
                mais antiga. Exibimos 20 por vez.
              </p>
            </div>
          </section>

          <section className="filters-panel">
            <form
              className="search-form"
              onSubmit={(event) => event.preventDefault()}
            >
              <label htmlFor="x-search" className="filter-label">
                Pesquisar no histórico
              </label>

              <div className="search-row">
                <input
                  id="x-search"
                  type="search"
                  value={buscaX}
                  onChange={(event) => setBuscaX(event.target.value)}
                  placeholder="Ex.: Hulk, Scarpa, Arena MRV, treino..."
                  aria-label="Buscar publicações no X"
                />
                <button type="submit">Pesquisar</button>
              </div>
            </form>

            <div className="filter-source-row">
              <label>
                <span className="filter-label">Perfil</span>
                <select
                  value={perfilSelecionadoX}
                  onChange={(event) => setPerfilSelecionadoX(event.target.value)}
                  aria-label="Filtrar timeline por perfil do X"
                >
                  <option value="">Todos os perfis</option>
                  {perfisX.map((conta) => (
                    <option value={conta.usuario} key={conta.id}>
                      {conta.nome} (@{conta.usuario})
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </section>

          {erroX && (
            <div className="state-card error-card">
              <strong>Não foi possível carregar a timeline.</strong>
              <span>Verifique se o backend está rodando em {API_URL}. Detalhe: {erroX}</span>
            </div>
          )}

          {!erroX && statusX?.fonte === "x_api_v2" && !statusX.token_configurado && (
            <div className="state-card error-card">
              <strong>Integração oficial do X sem credencial.</strong>
              <span>A fonte oficial foi selecionada, mas o servidor não possui Bearer Token.</span>
            </div>
          )}

          {!erroX && statusX && statusX.posts_total === 0 && (
            <div className="state-card">
              <strong>Perfis configurados; aguardando a primeira coleta.</strong>
              <span>O Radar do X ainda não gravou publicações no cache.</span>
            </div>
          )}

          {!erroX && carregandoX && feedX.length === 0 && (
            <div className="state-card">
              <strong>Carregando timeline do X...</strong>
            </div>
          )}

          {!erroX && !carregandoX && feedX.length === 0 && statusX && statusX.posts_total > 0 && (
            <div className="state-card">
              <strong>Nenhuma publicação encontrada para este perfil.</strong>
              <span>Escolha outro perfil ou volte para “Todos os perfis”.</span>
            </div>
          )}

          {!erroX &&
            !carregandoX &&
            feedX.length > 0 &&
            Boolean(buscaX.trim()) &&
            feedXFiltrado.length === 0 && (
              <div className="state-card">
                <strong>Nenhuma publicação encontrada.</strong>
                <span>Tente outro termo de busca.</span>
              </div>
          )}

          {!erroX && !carregandoX && feedXFiltrado.length > 0 && (
            <>
              <section className="x-timeline-list" aria-label="Timeline de publicações do X">
                {feedXFiltrado.map((post) => (
                  <XTimelineItem post={post} key={post.id} />
                ))}
              </section>

              <div className="x-timeline-load-more">
                {temMaisX ? (
                  <button
                    className="load-more-button"
                    type="button"
                    onClick={() => carregarFeedX({ append: true })}
                    disabled={carregandoMaisX}
                  >
                    {carregandoMaisX ? "Carregando..." : "Carregar mais publicações"}
                  </button>
                ) : (
                  <span>Você chegou ao fim das publicações armazenadas.</span>
                )}
              </div>
            </>
          )}
        </>
      )}

      {secaoAtiva === "jogos" && (
        <>
          <section className="section-header games-section-header">
            <div>
              <p className="eyebrow">CALENDÁRIO DO GALO</p>
              <h2>Jogos</h2>
              <p className="games-section-copy">
                Agenda, resultados e detalhes das partidas do Atlético.
              </p>
            </div>

            <button
              className="refresh-button"
              type="button"
              onClick={() => carregarJogos(mesJogos)}
              disabled={carregandoJogos}
            >
              {carregandoJogos ? "Atualizando..." : "Atualizar"}
            </button>
          </section>

          <section className="games-calendar-shell">
            <div className="games-calendar-toolbar">
              <div>
                <span className="games-calendar-kicker">VISÃO MENSAL</span>
                <h3>
                  {MESES_PT[mesJogos.getMonth()]} {mesJogos.getFullYear()}
                </h3>
              </div>

              <div className="games-calendar-actions">
                <button
                  type="button"
                  onClick={() =>
                    setMesJogos(
                      new Date(
                        mesJogos.getFullYear(),
                        mesJogos.getMonth() - 1,
                        1
                      )
                    )
                  }
                  aria-label="Mês anterior"
                >
                  ←
                </button>

                <button
                  className="games-calendar-today"
                  type="button"
                  onClick={() => setMesJogos(inicioDoMes(new Date()))}
                >
                  Hoje
                </button>

                <button
                  type="button"
                  onClick={() =>
                    setMesJogos(
                      new Date(
                        mesJogos.getFullYear(),
                        mesJogos.getMonth() + 1,
                        1
                      )
                    )
                  }
                  aria-label="Próximo mês"
                >
                  →
                </button>
              </div>
            </div>

            <div className="games-calendar-legend" aria-label="Legenda">
              <span><i className="legend-win" /> Vitória</span>
              <span><i className="legend-draw" /> Empate</span>
              <span><i className="legend-loss" /> Derrota</span>
              <span><i className="legend-future" /> Próximo jogo</span>
            </div>

            {erroJogos && (
              <div className="state-card error-card games-state">
                <strong>Não foi possível carregar os jogos.</strong>
                <span>{erroJogos}</span>
              </div>
            )}

            {!erroJogos && carregandoJogos && jogosCalendario.length === 0 && (
              <div className="state-card games-state">
                <strong>Carregando calendário...</strong>
              </div>
            )}

            {!erroJogos && !carregandoJogos && statusJogos?.total === 0 && (
              <div className="state-card games-state">
                <strong>Ainda não há jogos sincronizados.</strong>
                <span>
                  Execute a importação inicial da API-Football no backend.
                </span>
              </div>
            )}

            <div className="games-week-header">
              {DIAS_SEMANA.map((dia) => (
                <div key={dia}>{dia}</div>
              ))}
            </div>

            <div className="games-calendar-grid">
              {(() => {
                const primeiro = inicioDoMes(mesJogos);
                const ultimo = fimDoMes(mesJogos);
                const inicioGrade = new Date(primeiro);
                inicioGrade.setDate(primeiro.getDate() - primeiro.getDay());

                const fimGrade = new Date(ultimo);
                fimGrade.setDate(
                  ultimo.getDate() + (6 - ultimo.getDay())
                );

                const porData = new Map<string, JogoCalendario[]>();

                jogosCalendario.forEach((jogo) => {
                  const dataJogo = new Date(jogo.inicio_em);
                  const chave = chaveDataLocal(dataJogo);
                  const atuais = porData.get(chave) ?? [];
                  atuais.push(jogo);
                  porData.set(chave, atuais);
                });

                const dias: Date[] = [];
                const cursor = new Date(inicioGrade);

                while (cursor <= fimGrade) {
                  dias.push(new Date(cursor));
                  cursor.setDate(cursor.getDate() + 1);
                }

                return dias.map((dia) => {
                  const chave = chaveDataLocal(dia);
                  const jogosDia = porData.get(chave) ?? [];
                  const jogo = jogosDia[0];
                  const pertenceAoMes =
                    dia.getMonth() === mesJogos.getMonth();
                  const hoje =
                    chave === chaveDataLocal(new Date());

                  return (
                    <button
                      className={[
                        "games-calendar-day",
                        pertenceAoMes ? "" : "is-outside",
                        hoje ? "is-today" : "",
                        resultadoClasse(jogo),
                        jogo ? "has-game" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      type="button"
                      key={chave}
                      onClick={() => {
                        if (jogo) setJogoSelecionado(jogo);
                      }}
                      disabled={!jogo}
                      aria-label={
                        jogo
                          ? `${dia.getDate()} - Atlético contra ${jogo.adversario.nome}`
                          : `${dia.getDate()}`
                      }
                    >
                      <div className="games-day-top">
                        <span className="games-day-number">
                          {dia.getDate()}
                        </span>

                        {jogo?.status === "agendado" && (
                          jogo.galo_logo_url ? (
                            <img
                              className="games-day-galo-logo"
                              src={jogo.galo_logo_url}
                              alt="Atlético"
                              referrerPolicy="no-referrer"
                            />
                          ) : (
                            <span className="games-day-galo-fallback">CAM</span>
                          )
                        )}
                      </div>

                      {jogo && (
                        <div className="games-day-event">
                          {jogo.status === "agendado" && (
                            <span className="games-reserved-mark">
                              JOGO
                            </span>
                          )}

                          {jogo.status === "ao_vivo" && (
                            <span className="games-live-mark">
                              AO VIVO
                            </span>
                          )}

                          <strong>
                            {jogo.status === "finalizado"
                              ? placarJogo(jogo)
                              : formatarHorarioJogo(jogo.inicio_em)}
                          </strong>

                          <span className="games-day-rival">
                            {jogo.adversario.logo_url && (
                              <img
                                src={jogo.adversario.logo_url}
                                alt=""
                                referrerPolicy="no-referrer"
                              />
                            )}
                            <span>{jogo.adversario.nome}</span>
                          </span>

                          {jogosDia.length > 1 && (
                            <small>+{jogosDia.length - 1} jogo</small>
                          )}
                        </div>
                      )}
                    </button>
                  );
                });
              })()}
            </div>
          </section>

          {jogoSelecionado && (
            <div
              className="game-detail-overlay"
              role="dialog"
              aria-modal="true"
              aria-label="Detalhes do jogo"
              onMouseDown={(event) => {
                if (event.target === event.currentTarget) {
                  setJogoSelecionado(null);
                }
              }}
            >
              <article className="game-detail-card">
                <button
                  className="game-detail-close"
                  type="button"
                  onClick={() => setJogoSelecionado(null)}
                  aria-label="Fechar detalhes"
                >
                  ×
                </button>

                <div className="game-detail-head">
                  <div>
                    <span className="game-detail-date">
                      {formatarDataCompletaJogo(
                        jogoSelecionado.inicio_em
                      )}
                    </span>
                    <h3>
                      {jogoSelecionado.competicao.nome ??
                        "Competição"}
                    </h3>
                    {jogoSelecionado.rodada && (
                      <span className="game-detail-round">
                        {jogoSelecionado.rodada}
                      </span>
                    )}
                  </div>

                  {jogoSelecionado.competicao.logo_url && (
                    <img
                      className="game-detail-competition-logo"
                      src={jogoSelecionado.competicao.logo_url}
                      alt=""
                      referrerPolicy="no-referrer"
                    />
                  )}
                </div>

                <div className="game-detail-scoreboard">
                  <div className="game-detail-team">
                    {jogoSelecionado.mandante.logo_url ? (
                      <img
                        src={jogoSelecionado.mandante.logo_url}
                        alt=""
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <div className="game-detail-logo-fallback">?</div>
                    )}
                    <strong>{jogoSelecionado.mandante.nome}</strong>
                  </div>

                  <div className="game-detail-center">
                    {jogoSelecionado.status === "finalizado" ? (
                      <>
                        <span>FINAL</span>
                        <strong>{placarJogo(jogoSelecionado)}</strong>
                      </>
                    ) : jogoSelecionado.status === "ao_vivo" ? (
                      <>
                        <span className="game-detail-live">AO VIVO</span>
                        <strong>{placarJogo(jogoSelecionado)}</strong>
                      </>
                    ) : (
                      <>
                        <span>HORÁRIO</span>
                        <strong>
                          {formatarHorarioJogo(
                            jogoSelecionado.inicio_em
                          )}
                        </strong>
                      </>
                    )}
                  </div>

                  <div className="game-detail-team">
                    {jogoSelecionado.visitante.logo_url ? (
                      <img
                        src={jogoSelecionado.visitante.logo_url}
                        alt=""
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <div className="game-detail-logo-fallback">?</div>
                    )}
                    <strong>{jogoSelecionado.visitante.nome}</strong>
                  </div>
                </div>

                <div className="game-detail-info">
                  <div>
                    <span>Horário</span>
                    <strong>
                      {formatarHorarioJogo(jogoSelecionado.inicio_em)}
                    </strong>
                  </div>
                  <div>
                    <span>Campeonato</span>
                    <strong>
                      {jogoSelecionado.competicao.nome ?? "—"}
                    </strong>
                  </div>
                  <div>
                    <span>Estádio</span>
                    <strong>
                      {jogoSelecionado.estadio ?? "A definir"}
                    </strong>
                    {jogoSelecionado.cidade && (
                      <small>{jogoSelecionado.cidade}</small>
                    )}
                  </div>
                </div>

                {jogoSelecionado.status === "finalizado" &&
                  jogoSelecionado.gols.length > 0 && (
                    <div className="game-goals-panel">
                      <div className="game-goals-title">
                        <span className="eyebrow">GOLS DA PARTIDA</span>
                        <strong>Quem marcou</strong>
                      </div>

                      <div className="game-goals-list">
                        {jogoSelecionado.gols.map((gol, index) => (
                          <div
                            className="game-goal-row"
                            key={`${gol.jogador}-${gol.minuto}-${index}`}
                          >
                            {gol.time_logo ? (
                              <img
                                src={gol.time_logo}
                                alt=""
                                referrerPolicy="no-referrer"
                              />
                            ) : (
                              <span className="game-goal-ball">⚽</span>
                            )}

                            <div>
                              <strong>
                                {gol.jogador ?? "Gol"}
                              </strong>
                              <span>
                                {gol.time ?? ""}
                                {gol.assistencia
                                  ? ` · assistência de ${gol.assistencia}`
                                  : ""}
                              </span>
                            </div>

                            <time>
                              {gol.minuto ?? "?"}
                              {gol.acrescimos
                                ? `+${gol.acrescimos}`
                                : ""}
                              '
                            </time>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {jogoSelecionado.status === "finalizado" &&
                  jogoSelecionado.gols.length === 0 && (
                    <div className="game-goals-empty">
                      Autores dos gols ainda não sincronizados para esta partida.
                    </div>
                  )}
              </article>
            </div>
          )}
        </>
      )}

      <style jsx global>{`
        .site-cover-overlay {
          position: fixed;
          inset: 0;
          z-index: 99999;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
          background: rgba(0, 0, 0, 0.82);
          backdrop-filter: blur(6px);
        }

        .site-cover-modal {
          position: relative;
          width: min(100%, 980px);
          max-height: calc(100vh - 48px);
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 18px;
          overflow: hidden;
          background: #000;
          box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
        }

        .site-cover-media {
          display: block;
          width: 100%;
          max-height: calc(100vh - 48px);
          object-fit: contain;
          background: #000;
        }

        .site-cover-close {
          position: absolute;
          top: 12px;
          right: 12px;
          z-index: 2;
          width: 42px;
          height: 42px;
          border: 0;
          border-radius: 999px;
          background: rgba(0, 0, 0, 0.72);
          color: #fff;
          font-size: 30px;
          line-height: 1;
          cursor: pointer;
        }

        .site-cover-close:hover {
          background: rgba(0, 0, 0, 0.92);
        }

        .games-section-header {
          align-items: flex-end;
        }

        .games-section-copy {
          margin: 8px 0 0;
          color: #6b7280;
        }

        .games-calendar-shell {
          margin-top: 20px;
          overflow: hidden;
          border: 1px solid #e5e7eb;
          border-radius: 24px;
          background: #ffffff;
          box-shadow: 0 18px 50px rgba(15, 23, 42, 0.07);
        }

        .games-calendar-toolbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 18px;
          padding: 24px 26px 18px;
          border-bottom: 1px solid #eef0f3;
        }

        .games-calendar-kicker {
          display: block;
          margin-bottom: 4px;
          font-size: 11px;
          font-weight: 800;
          letter-spacing: 0.14em;
          color: #858b94;
        }

        .games-calendar-toolbar h3 {
          margin: 0;
          font-size: clamp(24px, 3vw, 34px);
          letter-spacing: -0.04em;
        }

        .games-calendar-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .games-calendar-actions button {
          min-width: 42px;
          height: 42px;
          padding: 0 13px;
          border: 1px solid #d8dce2;
          border-radius: 12px;
          background: #ffffff;
          color: #111827;
          font-weight: 800;
          cursor: pointer;
        }

        .games-calendar-actions button:hover {
          background: #f5f6f8;
        }

        .games-calendar-actions .games-calendar-today {
          min-width: 70px;
        }

        .games-calendar-legend {
          display: flex;
          flex-wrap: wrap;
          gap: 16px;
          padding: 14px 26px;
          border-bottom: 1px solid #eef0f3;
          background: #fafafa;
          color: #626873;
          font-size: 12px;
          font-weight: 700;
        }

        .games-calendar-legend span {
          display: inline-flex;
          align-items: center;
          gap: 7px;
        }

        .games-calendar-legend i {
          width: 11px;
          height: 11px;
          border-radius: 50%;
        }

        .legend-win {
          background: #ccefd5;
          border: 1px solid #82cc95;
        }

        .legend-draw {
          background: #d5ab42;
        }

        .legend-loss {
          background: #111111;
        }

        .legend-future {
          background: #ffffff;
          border: 2px solid #111111;
        }

        .games-week-header {
          display: grid;
          grid-template-columns: repeat(7, minmax(0, 1fr));
          border-bottom: 1px solid #e9ebef;
          background: #f7f8fa;
        }

        .games-week-header div {
          padding: 12px 10px;
          text-align: center;
          color: #808690;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: 0.08em;
        }

        .games-calendar-grid {
          display: grid;
          grid-template-columns: repeat(7, minmax(0, 1fr));
          background: #e5e7eb;
          gap: 1px;
        }

        .games-calendar-day {
          position: relative;
          min-height: 142px;
          padding: 12px;
          border: 0;
          border-radius: 0;
          background: #ffffff;
          color: #111827;
          text-align: left;
          cursor: default;
          transition:
            transform 140ms ease,
            box-shadow 140ms ease,
            filter 140ms ease;
        }

        .games-calendar-day.has-game {
          cursor: pointer;
        }

        .games-calendar-day.has-game:hover {
          z-index: 2;
          transform: translateY(-2px);
          box-shadow: 0 12px 32px rgba(0, 0, 0, 0.14);
          filter: brightness(1.01);
        }

        .games-calendar-day:disabled {
          opacity: 1;
        }

        .games-calendar-day.is-outside {
          background: #f8f8f9;
          color: #b0b4bb;
        }

        .games-calendar-day.game-day-win {
          background: #dff4e4;
          color: #102d18;
        }

        .games-calendar-day.game-day-draw {
          background: #d7b354;
          color: #211a07;
        }

        .games-calendar-day.game-day-loss {
          background: #111111;
          color: #ffffff;
        }

        .games-calendar-day.game-day-live {
          background: #fff0f0;
          color: #4e1212;
        }

        .games-calendar-day.game-day-future {
          background:
            linear-gradient(180deg, #ffffff 0%, #ffffff 70%, #fafafa 100%);
        }

        .games-calendar-day.is-today::after {
          content: "";
          position: absolute;
          inset: 5px;
          border: 2px solid #111111;
          border-radius: 14px;
          pointer-events: none;
        }

        .games-day-top {
          position: relative;
          z-index: 1;
          display: flex;
          align-items: center;
          gap: 8px;
          min-height: 30px;
        }

        .games-day-number {
          font-size: 15px;
          font-weight: 900;
        }

        .games-day-galo-logo {
          width: 26px;
          height: 26px;
          object-fit: contain;
        }

        .games-day-galo-fallback {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          border-radius: 50%;
          background: #111111;
          color: #ffffff;
          font-size: 9px;
          font-weight: 900;
        }

        .games-day-event {
          position: relative;
          z-index: 1;
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 5px;
          margin-top: 12px;
        }

        .games-day-event > strong {
          font-size: 17px;
          letter-spacing: -0.02em;
        }

        .games-reserved-mark {
          position: relative;
          width: 100%;
          padding-top: 7px;
          color: #111111;
          font-size: 9px;
          font-weight: 950;
          letter-spacing: 0.15em;
        }

        .games-reserved-mark::before {
          content: "";
          position: absolute;
          top: 0;
          left: 0;
          width: 42px;
          height: 3px;
          border-radius: 999px;
          background: #111111;
        }

        .games-live-mark {
          display: inline-flex;
          padding: 4px 7px;
          border-radius: 999px;
          background: #c91616;
          color: #ffffff;
          font-size: 9px;
          font-weight: 950;
          letter-spacing: 0.08em;
        }

        .games-day-rival {
          display: flex;
          align-items: center;
          gap: 6px;
          width: 100%;
          min-width: 0;
          font-size: 11px;
          font-weight: 750;
        }

        .games-day-rival img {
          flex: 0 0 auto;
          width: 18px;
          height: 18px;
          object-fit: contain;
        }

        .games-day-rival span {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .game-day-loss .games-day-rival,
        .game-day-loss .games-day-event small {
          color: #e5e7eb;
        }

        .games-day-event small {
          color: #737983;
          font-size: 10px;
        }

        .games-state {
          margin: 18px 24px;
        }

        .game-detail-overlay {
          position: fixed;
          inset: 0;
          z-index: 99990;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 22px;
          background: rgba(0, 0, 0, 0.72);
          backdrop-filter: blur(6px);
        }

        .game-detail-card {
          position: relative;
          width: min(100%, 760px);
          max-height: calc(100vh - 44px);
          overflow-y: auto;
          padding: 28px;
          border-radius: 24px;
          background: #ffffff;
          box-shadow: 0 28px 90px rgba(0, 0, 0, 0.42);
        }

        .game-detail-close {
          position: absolute;
          top: 14px;
          right: 14px;
          z-index: 3;
          width: 40px;
          height: 40px;
          border: 0;
          border-radius: 50%;
          background: #111111;
          color: #ffffff;
          font-size: 28px;
          cursor: pointer;
        }

        .game-detail-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 20px;
          padding-right: 48px;
        }

        .game-detail-date {
          display: block;
          margin-bottom: 6px;
          color: #777d86;
          font-size: 13px;
          text-transform: capitalize;
        }

        .game-detail-head h3 {
          margin: 0;
          font-size: 25px;
          letter-spacing: -0.03em;
        }

        .game-detail-round {
          display: block;
          margin-top: 6px;
          color: #777d86;
          font-size: 12px;
        }

        .game-detail-competition-logo {
          width: 54px;
          height: 54px;
          object-fit: contain;
        }

        .game-detail-scoreboard {
          display: grid;
          grid-template-columns: 1fr 110px 1fr;
          align-items: center;
          gap: 18px;
          margin-top: 28px;
          padding: 24px 18px;
          border-radius: 18px;
          background: #f6f7f8;
        }

        .game-detail-team {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 10px;
          min-width: 0;
          text-align: center;
        }

        .game-detail-team img,
        .game-detail-logo-fallback {
          width: 72px;
          height: 72px;
          object-fit: contain;
        }

        .game-detail-logo-fallback {
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 50%;
          background: #e5e7eb;
          font-weight: 900;
        }

        .game-detail-team strong {
          font-size: 14px;
        }

        .game-detail-center {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          text-align: center;
        }

        .game-detail-center span {
          color: #777d86;
          font-size: 9px;
          font-weight: 900;
          letter-spacing: 0.14em;
        }

        .game-detail-center strong {
          font-size: 28px;
          letter-spacing: -0.05em;
        }

        .game-detail-center .game-detail-live {
          color: #c91616;
        }

        .game-detail-info {
          display: grid;
          grid-template-columns: 110px minmax(0, 1fr) minmax(0, 1fr);
          gap: 12px;
          margin-top: 18px;
        }

        .game-detail-info > div {
          display: flex;
          flex-direction: column;
          gap: 3px;
          min-width: 0;
          padding: 14px;
          border: 1px solid #e5e7eb;
          border-radius: 14px;
        }

        .game-detail-info span {
          color: #7a8089;
          font-size: 10px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }

        .game-detail-info strong {
          font-size: 13px;
        }

        .game-detail-info small {
          color: #777d86;
          font-size: 11px;
        }

        .game-goals-panel {
          margin-top: 20px;
          border: 1px solid #e5e7eb;
          border-radius: 18px;
          overflow: hidden;
        }

        .game-goals-title {
          display: flex;
          flex-direction: column;
          gap: 2px;
          padding: 16px 18px;
          border-bottom: 1px solid #e5e7eb;
          background: #fafafa;
        }

        .game-goals-list {
          display: flex;
          flex-direction: column;
        }

        .game-goal-row {
          display: grid;
          grid-template-columns: 34px 1fr auto;
          align-items: center;
          gap: 10px;
          padding: 13px 18px;
          border-bottom: 1px solid #eef0f2;
        }

        .game-goal-row:last-child {
          border-bottom: 0;
        }

        .game-goal-row img {
          width: 28px;
          height: 28px;
          object-fit: contain;
        }

        .game-goal-row > div {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .game-goal-row > div strong {
          font-size: 13px;
        }

        .game-goal-row > div span {
          color: #777d86;
          font-size: 11px;
        }

        .game-goal-row time {
          font-weight: 900;
        }

        .game-goal-ball {
          font-size: 20px;
        }

        .game-goals-empty {
          margin-top: 18px;
          padding: 14px 16px;
          border-radius: 14px;
          background: #f6f7f8;
          color: #777d86;
          font-size: 12px;
        }

        @media (max-width: 860px) {
          .games-calendar-day {
            min-height: 112px;
            padding: 9px;
          }

          .games-day-rival {
            font-size: 9px;
          }

          .games-day-event > strong {
            font-size: 14px;
          }
        }

        @media (max-width: 680px) {
          .games-calendar-shell {
            overflow-x: auto;
          }

          .games-calendar-toolbar {
            min-width: 720px;
          }

          .games-calendar-legend,
          .games-week-header,
          .games-calendar-grid {
            min-width: 720px;
          }

          .game-detail-scoreboard {
            grid-template-columns: 1fr 84px 1fr;
          }

          .game-detail-team img,
          .game-detail-logo-fallback {
            width: 54px;
            height: 54px;
          }

          .game-detail-center strong {
            font-size: 22px;
          }

          .game-detail-info {
            grid-template-columns: 1fr;
          }
        }

        .youtube-live-badge.is-live-now {
          background: #15803d !important;
          color: #ffffff !important;
          border-color: #15803d !important;
          animation: central-galo-live-pulse 1.8s ease-in-out infinite;
        }

        @keyframes central-galo-live-pulse {
          0%,
          100% {
            box-shadow: 0 0 0 0 rgba(21, 128, 61, 0.35);
          }
          50% {
            box-shadow: 0 0 0 7px rgba(21, 128, 61, 0);
          }
        }
      `}</style>
    </main>
  );
}
