create table if not exists public.paginas (
    id uuid primary key default gen_random_uuid(),
    titulo text not null,
    slug text not null unique,
    conteudo text not null,
    ativo boolean not null default true,
    criado_em timestamptz not null default now(),
    atualizado_em timestamptz not null default now(),
    constraint paginas_slug_formato check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$')
);

create index if not exists idx_paginas_ativo_slug
    on public.paginas (ativo, slug);

alter table public.paginas enable row level security;
