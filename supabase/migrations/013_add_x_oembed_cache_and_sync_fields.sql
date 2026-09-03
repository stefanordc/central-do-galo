-- Cache de posts do X + oEmbed nativo.
-- Esta migration já foi aplicada no projeto Supabase do Central do Galo.

alter table public.contas_x
    add column if not exists x_user_id text,
    add column if not exists foto_url text,
    add column if not exists ultimo_post_id text,
    add column if not exists ultima_sincronizacao timestamptz,
    add column if not exists status_sync text not null default 'pendente',
    add column if not exists sync_erro text,
    add column if not exists atualizado_em timestamptz not null default now();

alter table public.posts_x
    add column if not exists embed_html text,
    add column if not exists embed_status text not null default 'pendente',
    add column if not exists embed_atualizado_em timestamptz,
    add column if not exists metricas jsonb not null default '{}'::jsonb,
    add column if not exists midia jsonb not null default '[]'::jsonb;

create index if not exists idx_posts_x_conta_publicado
    on public.posts_x (conta_id, publicado_em desc);

create index if not exists idx_posts_x_publicado_ativo
    on public.posts_x (publicado_em desc)
    where ativo = true;

create index if not exists idx_contas_x_sync
    on public.contas_x (ativo, ultima_sincronizacao);

create or replace function public.set_contas_x_atualizado_em()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.atualizado_em = now();
    return new;
end;
$$;

drop trigger if exists trg_contas_x_atualizado_em on public.contas_x;
create trigger trg_contas_x_atualizado_em
before update on public.contas_x
for each row execute function public.set_contas_x_atualizado_em();
