"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

const API_URL = "/backend";

type Pagina = {
  id: string;
  titulo: string;
  slug: string;
  conteudo: string;
  criado_em: string;
  atualizado_em: string;
};

export default function PaginaPublica() {
  const params = useParams<{ slug: string }>();
  const slug = params?.slug ?? "";
  const [pagina, setPagina] = useState<Pagina | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    fetch(`${API_URL}/api/paginas/${encodeURIComponent(slug)}`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Página não encontrada.");
        return response.json();
      })
      .then((data: Pagina) => {
        setPagina(data);
        setErro(null);
      })
      .catch((error) => setErro(error instanceof Error ? error.message : "Página não encontrada."));
  }, [slug]);

  return (
    <main className="public-page-shell">
      <a className="public-page-brand" href="/">
        <img src="/central-do-galo-logo.png" alt="Central do Galo" />
        <span>Central do Galo</span>
      </a>
      {erro ? (
        <section className="public-page-content">
          <span className="eyebrow">CENTRAL DO GALO</span>
          <h1>Página não encontrada</h1>
          <p>{erro}</p>
        </section>
      ) : !pagina ? (
        <section className="public-page-content"><p>Carregando...</p></section>
      ) : (
        <article className="public-page-content">
          <span className="eyebrow">CENTRAL DO GALO</span>
          <h1>{pagina.titulo}</h1>
          <div className="public-page-body">{pagina.conteudo}</div>
        </article>
      )}
    </main>
  );
}
