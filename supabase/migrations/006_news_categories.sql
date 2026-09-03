create table if not exists public.categorias (
    id uuid primary key default gen_random_uuid(),
    nome text not null,
    slug text not null unique,
    descricao text,
    ordem smallint not null default 100,
    ativo boolean not null default true,
    criado_em timestamptz not null default now(),
    atualizado_em timestamptz not null default now()
);

create table if not exists public.noticias_categorias (
    noticia_id uuid not null references public.noticias(id) on delete cascade,
    categoria_id uuid not null references public.categorias(id) on delete cascade,
    principal boolean not null default false,
    origem text not null default 'regra' check (origem in ('regra','manual','ia')),
    confianca numeric(5,4) not null default 1.0 check (confianca between 0 and 1),
    criado_em timestamptz not null default now(),
    primary key (noticia_id, categoria_id)
);

create index if not exists idx_noticias_categorias_categoria
on public.noticias_categorias(categoria_id, noticia_id);

alter table public.categorias enable row level security;
alter table public.noticias_categorias enable row level security;

grant select on table public.categorias to anon, authenticated;
grant select on table public.noticias_categorias to anon, authenticated;

create policy "leitura_publica_categorias" on public.categorias
for select to anon, authenticated using (ativo = true);

create policy "leitura_publica_noticias_categorias" on public.noticias_categorias
for select to anon, authenticated using (true);

create trigger trg_categorias_atualizado_em
before update on public.categorias
for each row execute function public.set_atualizado_em();

insert into public.categorias (nome, slug, descricao, ordem)
values
('Pré-jogo','pre-jogo','Escalações, preparação, desfalques, arbitragem e expectativa antes das partidas.',10),
('Pós-jogo','pos-jogo','Resultado, análise e repercussão depois das partidas.',20),
('Financeiro','financeiro','Receitas, vendas, premiações, orçamento, SAF e valores ligados ao clube.',30),
('Mercado','mercado','Contratações, saídas, propostas, renovações e transferências.',40),
('Departamento médico','departamento-medico','Lesões, recuperação, exames, cirurgias e retornos.',50),
('Treinos','treinos','Treinos, reapresentações e preparação do elenco.',60),
('Entrevistas','entrevistas','Entrevistas, declarações e coletivas.',70),
('Bastidores','bastidores','Ambiente interno, decisões e gestão esportiva.',80),
('Institucional','institucional','Comunicados, diretoria e assuntos institucionais.',90),
('Arena MRV','arena-mrv','Arena MRV, ingressos, operação, eventos e infraestrutura.',100),
('Base','base','Categorias de base e jovens atletas.',110),
('Futebol feminino','futebol-feminino','Futebol feminino do Atlético.',120),
('Torcida','torcida','Torcida, ingressos, mosaicos, caravanas e experiências.',130),
('Geral','geral','Notícias que não se encaixam nas demais categorias.',999)
on conflict (slug) do update
set nome=excluded.nome,
    descricao=excluded.descricao,
    ordem=excluded.ordem,
    ativo=true,
    atualizado_em=now();
