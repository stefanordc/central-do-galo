"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

const API_URL = "/backend";
const ADMIN_EMAIL = "stefanobrunofaria@gmail.com";

type PaginaAdmin = {
  id: string;
  titulo: string;
  slug: string;
  conteudo: string;
  ativo: boolean;
  criado_em: string;
};

type ContaXAdmin = {
  id: string;
  nome: string;
  usuario: string;
  oficial: boolean;
  confiabilidade: number;
  ativo: boolean;
  status_sync: string;
  ultima_sincronizacao: string | null;
};

function slugify(valor: string): string {
  return valor
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState(ADMIN_EMAIL);
  const [senha, setSenha] = useState("");
  const [erroLogin, setErroLogin] = useState<string | null>(null);
  const [carregandoLogin, setCarregandoLogin] = useState(false);
  const [paginas, setPaginas] = useState<PaginaAdmin[]>([]);
  const [contas, setContas] = useState<ContaXAdmin[]>([]);
  const [mensagem, setMensagem] = useState<string | null>(null);

  const [tituloPagina, setTituloPagina] = useState("");
  const [slugPagina, setSlugPagina] = useState("");
  const [slugEditado, setSlugEditado] = useState(false);
  const [conteudoPagina, setConteudoPagina] = useState("");

  const [nomeX, setNomeX] = useState("");
  const [usuarioX, setUsuarioX] = useState("");
  const [oficialX, setOficialX] = useState(false);
  const [confiabilidadeX, setConfiabilidadeX] = useState(80);

  const authHeaders = useMemo(
    () => (token ? { Authorization: `Bearer ${token}` } : {}),
    [token]
  );

  useEffect(() => {
    const salvo = window.sessionStorage.getItem("central_galo_admin_token") ?? "";
    if (salvo) setToken(salvo);
  }, []);

  useEffect(() => {
    if (!token) return;
    carregarDados();
  }, [token]);

  async function carregarDados() {
    const headers = { ...authHeaders };
    const [paginasResponse, contasResponse] = await Promise.all([
      fetch(`${API_URL}/api/admin/paginas`, { headers, cache: "no-store" }),
      fetch(`${API_URL}/api/admin/x/contas`, { headers, cache: "no-store" }),
    ]);

    if (paginasResponse.status === 401 || contasResponse.status === 401) {
      sair();
      return;
    }

    if (paginasResponse.ok) setPaginas(await paginasResponse.json());
    if (contasResponse.ok) setContas(await contasResponse.json());
  }

  async function entrar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCarregandoLogin(true);
    setErroLogin(null);

    try {
      const response = await fetch(`${API_URL}/api/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, senha }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail ?? "Não foi possível entrar.");
      window.sessionStorage.setItem("central_galo_admin_token", body.token);
      setToken(body.token);
      setSenha("");
    } catch (error) {
      setErroLogin(error instanceof Error ? error.message : "Falha no login.");
    } finally {
      setCarregandoLogin(false);
    }
  }

  function sair() {
    window.sessionStorage.removeItem("central_galo_admin_token");
    setToken("");
    setPaginas([]);
    setContas([]);
  }

  async function criarPagina(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMensagem(null);
    const response = await fetch(`${API_URL}/api/admin/paginas`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({
        titulo: tituloPagina,
        slug: slugPagina || slugify(tituloPagina),
        conteudo: conteudoPagina,
        ativo: true,
      }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setMensagem(body.detail ?? "Não foi possível criar a página.");
      return;
    }
    setTituloPagina("");
    setSlugPagina("");
    setSlugEditado(false);
    setConteudoPagina("");
    setMensagem("Página criada.");
    await carregarDados();
  }

  async function criarContaX(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMensagem(null);
    const response = await fetch(`${API_URL}/api/admin/x/contas`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({
        nome: nomeX,
        usuario: usuarioX,
        oficial: oficialX,
        confiabilidade: confiabilidadeX,
      }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setMensagem(body.detail ?? "Não foi possível cadastrar o perfil.");
      return;
    }
    setNomeX("");
    setUsuarioX("");
    setOficialX(false);
    setConfiabilidadeX(80);
    setMensagem(`@${body.usuario} adicionado ao Radar do X.`);
    await carregarDados();
  }

  if (!token) {
    return (
      <main className="admin-shell admin-login-shell">
        <section className="admin-login-card">
          <div className="admin-brand-row">
            <img src="/central-do-galo-logo.png" alt="Central do Galo" />
            <div>
              <span className="eyebrow">ÁREA RESTRITA</span>
              <h1>Admin</h1>
            </div>
          </div>
          <p>Entre para gerenciar páginas e perfis monitorados no X.</p>
          <form className="admin-form" onSubmit={entrar}>
            <label>
              E-mail
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <label>
              Senha
              <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} required />
            </label>
            {erroLogin && <div className="admin-alert admin-alert-error">{erroLogin}</div>}
            <button className="admin-primary-button" type="submit" disabled={carregandoLogin}>
              {carregandoLogin ? "Entrando..." : "Entrar"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="admin-shell">
      <header className="admin-header">
        <div>
          <span className="eyebrow">CENTRAL DO GALO</span>
          <h1>Painel administrativo</h1>
          <p>Gerencie páginas públicas e os perfis usados pelo Radar do X.</p>
        </div>
        <button className="admin-secondary-button" type="button" onClick={sair}>Sair</button>
      </header>

      {mensagem && <div className="admin-alert">{mensagem}</div>}

      <section className="admin-grid">
        <article className="admin-panel">
          <div className="admin-panel-heading">
            <div>
              <span className="eyebrow">CONTEÚDO</span>
              <h2>Nova página</h2>
            </div>
            <span>{paginas.length} cadastrada(s)</span>
          </div>
          <form className="admin-form" onSubmit={criarPagina}>
            <label>
              Título
              <input
                value={tituloPagina}
                onChange={(e) => {
                  const valor = e.target.value;
                  setTituloPagina(valor);
                  if (!slugEditado) setSlugPagina(slugify(valor));
                }}
                placeholder="Ex.: Sobre o projeto"
                required
              />
            </label>
            <label>
              Slug
              <div className="admin-input-prefix">
                <span>/p/</span>
                <input
                  value={slugPagina}
                  onChange={(e) => {
                    setSlugEditado(true);
                    setSlugPagina(slugify(e.target.value));
                  }}
                  placeholder="sobre-o-projeto"
                  required
                />
              </div>
            </label>
            <label>
              Conteúdo
              <textarea
                value={conteudoPagina}
                onChange={(e) => setConteudoPagina(e.target.value)}
                rows={10}
                placeholder="Escreva o conteúdo da página..."
                required
              />
            </label>
            <button className="admin-primary-button" type="submit">Criar página</button>
          </form>

          <div className="admin-list">
            {paginas.map((pagina) => (
              <div className="admin-list-item" key={pagina.id}>
                <div>
                  <strong>{pagina.titulo}</strong>
                  <span>/p/{pagina.slug}</span>
                </div>
                <a href={`/p/${pagina.slug}`} target="_blank" rel="noopener noreferrer">Abrir ↗</a>
              </div>
            ))}
          </div>
        </article>

        <article className="admin-panel">
          <div className="admin-panel-heading">
            <div>
              <span className="eyebrow">RADAR DO X</span>
              <h2>Novo perfil</h2>
            </div>
            <span>{contas.filter((conta) => conta.ativo).length} ativo(s)</span>
          </div>
          <form className="admin-form" onSubmit={criarContaX}>
            <label>
              Nome exibido
              <input value={nomeX} onChange={(e) => setNomeX(e.target.value)} placeholder="Ex.: João Silva" />
            </label>
            <label>
              Usuário ou URL do X
              <input
                value={usuarioX}
                onChange={(e) => setUsuarioX(e.target.value)}
                placeholder="@usuario ou https://x.com/usuario"
                required
              />
            </label>
            <label>
              Confiabilidade
              <input
                type="number"
                min={0}
                max={100}
                value={confiabilidadeX}
                onChange={(e) => setConfiabilidadeX(Number(e.target.value))}
              />
            </label>
            <label className="admin-check-row">
              <input type="checkbox" checked={oficialX} onChange={(e) => setOficialX(e.target.checked)} />
              Perfil oficial
            </label>
            <button className="admin-primary-button" type="submit">Adicionar perfil</button>
          </form>

          <div className="admin-list">
            {contas.map((conta) => (
              <div className="admin-list-item" key={conta.id}>
                <div>
                  <strong>{conta.nome}</strong>
                  <span>@{conta.usuario} · {conta.status_sync}</span>
                </div>
                <a href={`https://x.com/${conta.usuario}`} target="_blank" rel="noopener noreferrer">X ↗</a>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
