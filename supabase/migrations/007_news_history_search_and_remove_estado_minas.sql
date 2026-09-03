-- No Ataque substitui Estado de Minas na Central do Galo.
delete from public.fontes where slug = 'estado-de-minas';

-- Busca textual simples e rápida no histórico de notícias.
create schema if not exists extensions;
create extension if not exists pg_trgm with schema extensions;

create index if not exists idx_noticias_titulo_trgm
on public.noticias using gin (titulo extensions.gin_trgm_ops);

create index if not exists idx_noticias_resumo_trgm
on public.noticias using gin (resumo extensions.gin_trgm_ops)
where resumo is not null;
